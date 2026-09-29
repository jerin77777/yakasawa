/**
 * @file main.c
 * @brief Industrial ESP32-S3 Wi-Fi & RS-485 Modbus Controller for Yaskawa GA700 VFD
 * 
 * Features:
 * - Wi-Fi SoftAP ("ESP32-GA700") + optional Station (STA) mode
 * - Prints ESP32 IP address prominently to serial log
 * - Embedded HTTP REST API Server with CORS support
 * - Frequency Read: Monitor Parameter U1-01 (Register 0x0040)
 * - Frequency Write: Active Reference (Register 0x0002)
 * - Drive Control: RUN and STOP commands
 * - Full telemetry read (U1-01, U1-02, U1-03 current, Drive status)
 * - Integrated lightweight Web UI fallback on http://<IP>/
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_system.h"
#include "nvs_flash.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_mac.h"
#include "esp_http_server.h"
#include "lwip/inet.h"
#include "ga700_modbus.h"
#include "param_handlers.h"

#ifndef MACSTR
#define MACSTR "%02x:%02x:%02x:%02x:%02x:%02x"
#endif

#ifndef MAC2STR
#define MAC2STR(a) (a)[0], (a)[1], (a)[2], (a)[3], (a)[4], (a)[5]
#endif

static const char *TAG = "GA700_APP";

// ============================================================================
// Wi-Fi Configuration
// ============================================================================
#define WIFI_AP_SSID        "ESP32-GA700"
#define WIFI_AP_PASS        "12345678"     // Minimum 8 characters for WPA2
#define WIFI_AP_CHANNEL     1
#define WIFI_AP_MAX_CONN    4

// Optional: Set your home/office Wi-Fi router credentials below for STA mode
// Leave WIFI_STA_SSID as "" to use SoftAP only (Default: SoftAP 192.168.4.1)
#define WIFI_STA_SSID       ""
#define WIFI_STA_PASS       ""

static char g_ap_ip_str[32] = "192.168.4.1";
static char g_sta_ip_str[32] = "Not Connected";
static bool g_sta_connected = false;

// ============================================================================
// Print Banner Helper
// ============================================================================
static void print_connection_banner(void)
{
    ESP_LOGI(TAG, "==================================================================");
    ESP_LOGI(TAG, "             >>> ESP32-S3 WI-FI COMMUNICATION READY <<<           ");
    ESP_LOGI(TAG, "==================================================================");
    ESP_LOGI(TAG, "  * SoftAP Network SSID  : %s", WIFI_AP_SSID);
    ESP_LOGI(TAG, "  * SoftAP Password      : %s", WIFI_AP_PASS);
    ESP_LOGI(TAG, "  * SoftAP IP Address    : %s", g_ap_ip_str);
    if (g_sta_connected) {
        ESP_LOGI(TAG, "  * Station Router SSID  : %s", WIFI_STA_SSID);
        ESP_LOGI(TAG, "  * Station IP Address   : %s", g_sta_ip_str);
    } else {
        ESP_LOGI(TAG, "  * Station Mode         : Standalone SoftAP mode active");
    }
    ESP_LOGI(TAG, "------------------------------------------------------------------");
    ESP_LOGI(TAG, "  FLUTTER CONNECTIVITY INSTRUCTIONS:");
    ESP_LOGI(TAG, "  1. Connect your PC / Phone to Wi-Fi: '%s' (Pass: %s)", WIFI_AP_SSID, WIFI_AP_PASS);
    ESP_LOGI(TAG, "     OR use Station IP if on the same local network.");
    ESP_LOGI(TAG, "  2. In your Flutter app, enter IP: %s (or %s)", g_ap_ip_str, g_sta_connected ? g_sta_ip_str : g_ap_ip_str);
    ESP_LOGI(TAG, "------------------------------------------------------------------");
    ESP_LOGI(TAG, "  REST API ENDPOINTS:");
    ESP_LOGI(TAG, "  - GET  /api/frequency       -> Read U1-01 (0x0040) Freq Monitor");
    ESP_LOGI(TAG, "  - POST /api/frequency       -> Write Active Reference (0x0002)");
    ESP_LOGI(TAG, "  - POST /api/run             -> RUN Drive (Forward)");
    ESP_LOGI(TAG, "  - POST /api/stop            -> STOP Drive");
    ESP_LOGI(TAG, "  - GET  /api/status          -> Full Telemetry & Drive State");
    ESP_LOGI(TAG, "  - GET  /api/param?addr=0x.. -> Read ANY Register Address/Code");
    ESP_LOGI(TAG, "  - POST /api/param           -> Write ANY Register Address/Value");
    ESP_LOGI(TAG, "==================================================================");
}

// ============================================================================
// Wi-Fi Event Handler
// ============================================================================
static void wifi_event_handler(void *arg, esp_event_base_t event_base,
                               int32_t event_id, void *event_data)
{
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_AP_STACONNECTED) {
        wifi_event_ap_staconnected_t *event = (wifi_event_ap_staconnected_t *)event_data;
        ESP_LOGI(TAG, "Client connected to SoftAP: MAC="MACSTR" AID=%d",
                 MAC2STR(event->mac), event->aid);
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_AP_STADISCONNECTED) {
        wifi_event_ap_stadisconnected_t *event = (wifi_event_ap_stadisconnected_t *)event_data;
        ESP_LOGI(TAG, "Client disconnected from SoftAP: MAC="MACSTR" AID=%d",
                 MAC2STR(event->mac), event->aid);
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        g_sta_connected = false;
        ESP_LOGW(TAG, "Disconnected from STA router, retrying connection...");
        esp_wifi_connect();
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *event = (ip_event_got_ip_t *)event_data;
        snprintf(g_sta_ip_str, sizeof(g_sta_ip_str), IPSTR, IP2STR(&event->ip_info.ip));
        g_sta_connected = true;
        ESP_LOGI(TAG, ">>> CONNECTED TO ROUTER! STA IP Address: %s <<<", g_sta_ip_str);
        print_connection_banner();
    }
}

static void wifi_init(void)
{
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());

    // Create SoftAP netif
    esp_netif_t *ap_netif = esp_netif_create_default_wifi_ap();

    // Query Default AP IP
    esp_netif_ip_info_t ip_info;
    if (esp_netif_get_ip_info(ap_netif, &ip_info) == ESP_OK) {
        snprintf(g_ap_ip_str, sizeof(g_ap_ip_str), IPSTR, IP2STR(&ip_info.ip));
    }

    bool enable_sta = (strlen(WIFI_STA_SSID) > 0);
    if (enable_sta) {
        esp_netif_create_default_wifi_sta();
    }

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT,
                                                        ESP_EVENT_ANY_ID,
                                                        &wifi_event_handler,
                                                        NULL,
                                                        NULL));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT,
                                                        IP_EVENT_STA_GOT_IP,
                                                        &wifi_event_handler,
                                                        NULL,
                                                        NULL));

    wifi_config_t ap_config = {
        .ap = {
            .ssid = WIFI_AP_SSID,
            .ssid_len = strlen(WIFI_AP_SSID),
            .channel = WIFI_AP_CHANNEL,
            .password = WIFI_AP_PASS,
            .max_connection = WIFI_AP_MAX_CONN,
            .authmode = (strlen(WIFI_AP_PASS) == 0) ? WIFI_AUTH_OPEN : WIFI_AUTH_WPA2_PSK,
        },
    };

    if (enable_sta) {
        ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_APSTA));
        wifi_config_t sta_config = { 0 };
        strncpy((char *)sta_config.sta.ssid, WIFI_STA_SSID, sizeof(sta_config.sta.ssid));
        strncpy((char *)sta_config.sta.password, WIFI_STA_PASS, sizeof(sta_config.sta.password));
        ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &sta_config));
    } else {
        ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));
    }

    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &ap_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(TAG, "Wi-Fi initialization finished.");
    print_connection_banner();
}

// ============================================================================
// HTTP Server & REST API Handlers
// ============================================================================

static esp_err_t set_cors_headers(httpd_req_t *req)
{
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Headers", "Content-Type, Authorization, Accept");
    httpd_resp_set_hdr(req, "Access-Control-Max-Age", "86400");
    return ESP_OK;
}

// Handle HTTP OPTIONS for CORS pre-flight
static esp_err_t options_handler(httpd_req_t *req)
{
    set_cors_headers(req);
    httpd_resp_set_status(req, "204 No Content");
    httpd_resp_send(req, NULL, 0);
    return ESP_OK;
}

/**
 * @brief GET /api/frequency
 * Reads parameter U1-01 (Register 0x0040) - Frequency Reference Monitor
 */
static esp_err_t api_get_frequency_handler(httpd_req_t *req)
{
    set_cors_headers(req);
    httpd_resp_set_type(req, "application/json");

    uint16_t raw_val = 0;
    float freq_hz = 0.0f;
    esp_err_t err = ga700_read_frequency_u1_01(&raw_val, &freq_hz);

    char resp[256];
    if (err == ESP_OK) {
        snprintf(resp, sizeof(resp),
            "{\"status\":\"ok\",\"parameter\":\"U1-01\",\"address\":\"0x0040\",\"frequency_hz\":%.2f,\"raw_value\":%u}",
            freq_hz, raw_val);
        return httpd_resp_send(req, resp, HTTPD_RESP_USE_STRLEN);
    } else {
        snprintf(resp, sizeof(resp),
            "{\"status\":\"error\",\"parameter\":\"U1-01\",\"address\":\"0x0040\",\"error\":\"%s\"}",
            esp_err_to_name(err));
        httpd_resp_set_status(req, "500 Internal Server Error");
        return httpd_resp_send(req, resp, HTTPD_RESP_USE_STRLEN);
    }
}

/**
 * @brief Helper to parse float frequency from JSON body or query string
 */
static bool parse_frequency_payload(httpd_req_t *req, float *out_freq_hz)
{
    if (out_freq_hz == NULL) return false;

    // 1. Check URL query parameters (e.g. ?hz=50.0 or ?frequency=50.0)
    size_t qry_len = httpd_req_get_url_query_len(req);
    if (qry_len > 0) {
        char *qry_str = malloc(qry_len + 1);
        if (qry_str != NULL) {
            if (httpd_req_get_url_query_str(req, qry_str, qry_len + 1) == ESP_OK) {
                char val_str[32];
                if (httpd_query_key_value(qry_str, "hz", val_str, sizeof(val_str)) == ESP_OK ||
                    httpd_query_key_value(qry_str, "frequency", val_str, sizeof(val_str)) == ESP_OK) {
                    *out_freq_hz = strtof(val_str, NULL);
                    free(qry_str);
                    return true;
                }
                if (httpd_query_key_value(qry_str, "raw", val_str, sizeof(val_str)) == ESP_OK) {
                    *out_freq_hz = atoi(val_str) / 100.0f;
                    free(qry_str);
                    return true;
                }
            }
            free(qry_str);
        }
    }

    // 2. Check JSON POST body (e.g. {"frequency": 50.0} or {"hz": 50.0} or {"raw": 5000})
    int total_len = req->content_len;
    if (total_len > 0 && total_len < 1024) {
        char body[256];
        int cur_len = 0;
        int received = 0;
        while (cur_len < total_len && cur_len < sizeof(body) - 1) {
            received = httpd_req_recv(req, body + cur_len, total_len - cur_len);
            if (received <= 0) break;
            cur_len += received;
        }
        body[cur_len] = '\0';

        char *pos = strstr(body, "\"frequency\"");
        if (!pos) pos = strstr(body, "\"hz\"");
        if (pos) {
            char *colon = strchr(pos, ':');
            if (colon) {
                *out_freq_hz = strtof(colon + 1, NULL);
                return true;
            }
        }

        pos = strstr(body, "\"raw\"");
        if (pos) {
            char *colon = strchr(pos, ':');
            if (colon) {
                *out_freq_hz = atoi(colon + 1) / 100.0f;
                return true;
            }
        }
    }

    return false;
}

/**
 * @brief POST /api/frequency
 * Writes target frequency strictly to Active Frequency Reference (Register 0x0002)
 */
static esp_err_t api_post_frequency_handler(httpd_req_t *req)
{
    set_cors_headers(req);
    httpd_resp_set_type(req, "application/json");

    float target_freq = 0.0f;
    if (!parse_frequency_payload(req, &target_freq)) {
        const char *err_resp = "{\"status\":\"error\",\"message\":\"Missing frequency in payload. Send JSON: {\\\"frequency\\\": 50.0}\"}";
        httpd_resp_set_status(req, "400 Bad Request");
        return httpd_resp_send(req, err_resp, HTTPD_RESP_USE_STRLEN);
    }

    if (target_freq < 0.0f || target_freq > 400.0f) {
        char err_resp[128];
        snprintf(err_resp, sizeof(err_resp), "{\"status\":\"error\",\"message\":\"Frequency %.2f out of bounds (0-400 Hz)\"}", target_freq);
        httpd_resp_set_status(req, "400 Bad Request");
        return httpd_resp_send(req, err_resp, HTTPD_RESP_USE_STRLEN);
    }

    uint16_t raw_val = (uint16_t)(target_freq * 100.0f + 0.5f);
    // Write ONLY into 0x0002 (Active Frequency Reference)
    esp_err_t err = ga700_set_frequency(target_freq);

    char resp[300];
    if (err == ESP_OK) {
        snprintf(resp, sizeof(resp),
            "{\"status\":\"ok\",\"register\":\"0x0002\",\"u1_01_monitor\":\"0x0040\",\"frequency_hz\":%.2f,\"raw_value\":%u}",
            target_freq, raw_val);
        return httpd_resp_send(req, resp, HTTPD_RESP_USE_STRLEN);
    } else {
        snprintf(resp, sizeof(resp),
            "{\"status\":\"error\",\"message\":\"Failed to write frequency to drive\",\"error\":\"%s\"}",
            esp_err_to_name(err));
        httpd_resp_set_status(req, "500 Internal Server Error");
        return httpd_resp_send(req, resp, HTTPD_RESP_USE_STRLEN);
    }
}

/**
 * @brief POST /api/run
 * Sends RUN FORWARD command (Register 0x0001, Bit 0 = 1)
 */
static esp_err_t api_post_run_handler(httpd_req_t *req)
{
    set_cors_headers(req);
    httpd_resp_set_type(req, "application/json");

    esp_err_t err = ga700_run_forward();
    char resp[256];
    if (err == ESP_OK) {
        snprintf(resp, sizeof(resp), "{\"status\":\"ok\",\"command\":\"RUN\",\"register\":\"0x0001\"}");
        return httpd_resp_send(req, resp, HTTPD_RESP_USE_STRLEN);
    } else {
        snprintf(resp, sizeof(resp), "{\"status\":\"error\",\"command\":\"RUN\",\"error\":\"%s\"}", esp_err_to_name(err));
        httpd_resp_set_status(req, "500 Internal Server Error");
        return httpd_resp_send(req, resp, HTTPD_RESP_USE_STRLEN);
    }
}

/**
 * @brief POST /api/stop
 * Sends STOP command (Register 0x0001, Bit 0 = 0)
 */
static esp_err_t api_post_stop_handler(httpd_req_t *req)
{
    set_cors_headers(req);
    httpd_resp_set_type(req, "application/json");

    esp_err_t err = ga700_stop();
    char resp[256];
    if (err == ESP_OK) {
        snprintf(resp, sizeof(resp), "{\"status\":\"ok\",\"command\":\"STOP\",\"register\":\"0x0001\"}");
        return httpd_resp_send(req, resp, HTTPD_RESP_USE_STRLEN);
    } else {
        snprintf(resp, sizeof(resp), "{\"status\":\"error\",\"command\":\"STOP\",\"error\":\"%s\"}", esp_err_to_name(err));
        httpd_resp_set_status(req, "500 Internal Server Error");
        return httpd_resp_send(req, resp, HTTPD_RESP_USE_STRLEN);
    }
}

/**
 * @brief GET /api/status
 * Returns full telemetry: U1-01 (0x0040), U1-02 (0x0041), U1-03 (0x0042), Drive Status
 */
static esp_err_t api_get_status_handler(httpd_req_t *req)
{
    set_cors_headers(req);
    httpd_resp_set_type(req, "application/json");

    uint16_t u1_01_raw = 0;
    float u1_01_hz = 0.0f;
    ga700_read_frequency_u1_01(&u1_01_raw, &u1_01_hz);

    uint16_t u1_02_raw = 0;
    float u1_02_hz = 0.0f;
    ga700_read_frequency_u1_02(&u1_02_raw, &u1_02_hz);

    uint16_t u1_03_raw = 0;
    float u1_03_amps = 0.0f;
    ga700_read_output_current_u1_03(&u1_03_raw, &u1_03_amps);

    ga700_telemetry_t telem = { 0 };
    ga700_read_telemetry(&telem);

    char resp[512];
    snprintf(resp, sizeof(resp),
        "{"
        "\"status\":\"ok\","
        "\"u1_01_freq_ref_hz\":%.2f,"
        "\"u1_01_raw\":%u,"
        "\"u1_02_output_freq_hz\":%.2f,"
        "\"u1_02_raw\":%u,"
        "\"u1_03_current_a\":%.2f,"
        "\"u1_03_raw\":%u,"
        "\"is_running\":%s,"
        "\"is_reverse\":%s,"
        "\"is_ready\":%s,"
        "\"is_fault\":%s,"
        "\"voltage_v\":%.1f,"
        "\"softap_ip\":\"%s\","
        "\"sta_ip\":\"%s\""
        "}",
        u1_01_hz, u1_01_raw,
        u1_02_hz, u1_02_raw,
        u1_03_amps, u1_03_raw,
        telem.is_running ? "true" : "false",
        telem.is_reverse ? "true" : "false",
        telem.is_ready ? "true" : "false",
        telem.is_fault ? "true" : "false",
        telem.output_voltage_v,
        g_ap_ip_str,
        g_sta_ip_str
    );

    return httpd_resp_send(req, resp, HTTPD_RESP_USE_STRLEN);
}

/**
 * @brief GET / (Embedded Browser Webpage for quick diagnosis)
 */
static esp_err_t index_html_handler(httpd_req_t *req)
{
    set_cors_headers(req);
    httpd_resp_set_type(req, "text/html");

    const char *html =
        "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Yaskawa GA700 VFD Controller</title>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<style>"
        "body{font-family:sans-serif;background:#0d1117;color:#c9d1d9;padding:20px;text-align:center;}"
        ".card{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:24px;max-width:500px;margin:20px auto;box-shadow:0 8px 24px rgba(0,0,0,0.5);}"
        "h1{color:#58a6ff;font-size:22px;margin-bottom:8px;}h2{color:#8b949e;font-size:14px;margin-top:0;}"
        ".val{font-size:42px;font-weight:bold;color:#3fb950;margin:15px 0;font-family:monospace;}"
        "button{padding:12px 24px;margin:8px;font-size:16px;font-weight:bold;border-radius:8px;cursor:pointer;border:none;}"
        ".btn-run{background:#238636;color:white;}.btn-stop{background:#da3633;color:white;}.btn-read{background:#1f6feb;color:white;}"
        "input{padding:10px;font-size:16px;width:120px;text-align:center;border-radius:6px;border:1px solid #30363d;background:#0d1117;color:#fff;}"
        ".meta{font-size:12px;color:#8b949e;margin-top:16px;}"
        "</style></head><body><div class='card'>"
        "<h1>Yaskawa GA700 VFD</h1>"
        "<h2>ESP32-S3 RS-485 Modbus Bridge</h2>"
        "<div class='meta'>U1-01 Read (0x0040)</div>"
        "<div class='val' id='freq'>--.-- Hz</div>"
        "<div><button class='btn-read' onclick='readFreq()'>Read U1-01</button></div>"
        "<div class='meta' style='margin-top:24px;'>Frequency Write (0x0002)</div>"
        "<div style='margin-top:10px;'>"
        "<input type='number' id='setHz' step='0.1' min='0' max='400' value='50.0'> Hz "
        "<button class='btn-read' onclick='writeFreq()'>Write 0x0002</button>"
        "</div>"
        "<div style='margin-top:24px;'>"
        "<button class='btn-run' onclick='cmd(\"run\")'>RUN</button>"
        "<button class='btn-stop' onclick='cmd(\"stop\")'>STOP</button>"
        "</div>"
        "<p id='status' class='meta' style='color:#58a6ff;'></p>"
        "</div>"
        "<script>"
        "async function readFreq(){const r=await fetch('/api/frequency');const d=await r.json();document.getElementById('freq').innerText=d.frequency_hz.toFixed(2)+' Hz';document.getElementById('status').innerText='Read U1-01 (0x0040): '+d.frequency_hz+' Hz';}"
        "async function writeFreq(){const hz=parseFloat(document.getElementById('setHz').value);const r=await fetch('/api/frequency?hz='+hz,{method:'POST'});const d=await r.json();document.getElementById('status').innerText='Written 0x0002: '+hz+' Hz';readFreq();}"
        "async function cmd(c){await fetch('/api/'+c,{method:'POST'});document.getElementById('status').innerText='Command '+c.toUpperCase()+' sent!';}"
        "readFreq();setInterval(readFreq,2000);"
        "</script></body></html>";

    return httpd_resp_send(req, html, HTTPD_RESP_USE_STRLEN);
}

static httpd_handle_t start_webserver(void)
{
    httpd_handle_t server = NULL;
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.max_uri_handlers = 20;
    config.lru_purge_enable = true;

    ESP_LOGI(TAG, "Starting HTTP Server on port: %d", config.server_port);
    if (httpd_start(&server, &config) == ESP_OK) {
        // Register Parameter REST API Endpoints (/api/param GET/POST/OPTIONS)
        register_param_api_endpoints(server);

        // OPTIONS preflight handlers for CORS
        httpd_uri_t uri_options = {
            .uri       = "/api/*",
            .method    = HTTP_OPTIONS,
            .handler   = options_handler,
            .user_ctx  = NULL
        };
        httpd_register_uri_handler(server, &uri_options);

        // GET /api/frequency (Read U1-01: 0x0040)
        httpd_uri_t uri_get_freq = {
            .uri       = "/api/frequency",
            .method    = HTTP_GET,
            .handler   = api_get_frequency_handler,
            .user_ctx  = NULL
        };
        httpd_register_uri_handler(server, &uri_get_freq);

        // POST /api/frequency (Write 0x0002)
        httpd_uri_t uri_post_freq = {
            .uri       = "/api/frequency",
            .method    = HTTP_POST,
            .handler   = api_post_frequency_handler,
            .user_ctx  = NULL
        };
        httpd_register_uri_handler(server, &uri_post_freq);

        // POST /api/run
        httpd_uri_t uri_post_run = {
            .uri       = "/api/run",
            .method    = HTTP_POST,
            .handler   = api_post_run_handler,
            .user_ctx  = NULL
        };
        httpd_register_uri_handler(server, &uri_post_run);

        // POST /api/stop
        httpd_uri_t uri_post_stop = {
            .uri       = "/api/stop",
            .method    = HTTP_POST,
            .handler   = api_post_stop_handler,
            .user_ctx  = NULL
        };
        httpd_register_uri_handler(server, &uri_post_stop);

        // GET /api/status (Full telemetry)
        httpd_uri_t uri_get_status = {
            .uri       = "/api/status",
            .method    = HTTP_GET,
            .handler   = api_get_status_handler,
            .user_ctx  = NULL
        };
        httpd_register_uri_handler(server, &uri_get_status);

        // GET / (Embedded diagnosis UI)
        httpd_uri_t uri_index = {
            .uri       = "/",
            .method    = HTTP_GET,
            .handler   = index_html_handler,
            .user_ctx  = NULL
        };
        httpd_register_uri_handler(server, &uri_index);

        return server;
    }

    ESP_LOGE(TAG, "Error starting HTTP server!");
    return NULL;
}

// ============================================================================
// Main Application Entry Point
// ============================================================================
void app_main(void)
{
    // 1. Initialize NVS (Required for Wi-Fi storage)
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    ESP_LOGI(TAG, "==================================================");
    ESP_LOGI(TAG, " Yaskawa GA700 RS-485 & Wi-Fi Controller Program");
    ESP_LOGI(TAG, "==================================================");

    // 2. RS-485 Modbus Configuration (Industrial ESP32-S3 board)
    ga700_config_t config = {
        .uart_port  = UART_NUM_2,
        .tx_pin     = GPIO_NUM_17,   // Onboard RS485 TX
        .rx_pin     = GPIO_NUM_18,   // Onboard RS485 RX
        .rts_pin    = GPIO_NUM_21,   // Onboard RS485 EN / RTS
        .baud_rate  = 9600,          // GA700 Parameter H5-02 = 3 (9600 bps)
        .parity     = UART_PARITY_DISABLE, // GA700 Parameter H5-03 = 0 (8-N-1)
        .slave_addr = 0x1F,          // 31 decimal (GA700 Parameter H5-01 = 1F hex)
        .timeout_ms = 1000
    };

    // Initialize RS-485 Driver
    ret = ga700_init(&config);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to initialize RS-485 driver!");
        return;
    }
    ESP_LOGI(TAG, "RS-485 Driver successfully initialized.");

    // 3. Initialize Wi-Fi Communication & Print IP
    wifi_init();

    // 4. Start HTTP Server for Flutter / Web clients
    start_webserver();

    // 5. Background Diagnostic Polling Loop (Periodically logs U1-01 and U1-03)
    uint32_t count = 0;
    while (1) {
        vTaskDelay(pdMS_TO_TICKS(5000));
        count++;

        uint16_t u1_01_raw = 0;
        float u1_01_hz = 0.0f;
        esp_err_t err1 = ga700_read_frequency_u1_01(&u1_01_raw, &u1_01_hz);

        uint16_t u1_03_raw = 0;
        float u1_03_amps = 0.0f;
        esp_err_t err2 = ga700_read_output_current_u1_03(&u1_03_raw, &u1_03_amps);

        if (err1 == ESP_OK && err2 == ESP_OK) {
            ESP_LOGI(TAG, "[Poll #%lu] U1-01 Freq: %.2f Hz (Raw: 0x%04X) | U1-03 Current: %.2f A | IP: %s",
                     count, u1_01_hz, u1_01_raw, u1_03_amps, g_ap_ip_str);
        } else {
            ESP_LOGD(TAG, "[Poll #%lu] Bus idle / Read status: U1-01=%s, U1-03=%s",
                     count, esp_err_to_name(err1), esp_err_to_name(err2));
        }
    }
}
