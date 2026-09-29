/**
 * @file param_handlers.c
 * @brief REST API Handlers for Reading and Writing Yaskawa GA700 Parameters
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "esp_log.h"
#include "esp_http_server.h"
#include "ga700_modbus.h"
#include "generated_params.h"
#include "param_handlers.h"

static const char *TAG = "PARAM_API";

static esp_err_t set_cors_headers(httpd_req_t *req)
{
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Headers", "Content-Type, Authorization, Accept");
    httpd_resp_set_hdr(req, "Access-Control-Max-Age", "86400");
    return ESP_OK;
}

static esp_err_t param_options_handler(httpd_req_t *req)
{
    set_cors_headers(req);
    httpd_resp_set_status(req, "204 No Content");
    httpd_resp_send(req, NULL, 0);
    return ESP_OK;
}

/**
 * Helper to parse target address from query string or JSON
 */
static bool parse_param_address(httpd_req_t *req, uint16_t *out_addr, const ga700_param_meta_t **out_meta)
{
    if (out_addr == NULL) return false;
    *out_addr = 0;
    if (out_meta) *out_meta = NULL;

    size_t qry_len = httpd_req_get_url_query_len(req);
    if (qry_len > 0) {
        char *qry = malloc(qry_len + 1);
        if (qry != NULL) {
            if (httpd_req_get_url_query_str(req, qry, qry_len + 1) == ESP_OK) {
                char val_str[64];
                // Check 'addr' or 'address'
                if (httpd_query_key_value(qry, "addr", val_str, sizeof(val_str)) == ESP_OK ||
                    httpd_query_key_value(qry, "address", val_str, sizeof(val_str)) == ESP_OK) {
                    if (strncmp(val_str, "0x", 2) == 0 || strncmp(val_str, "0X", 2) == 0) {
                        *out_addr = (uint16_t)strtoul(val_str, NULL, 16);
                    } else {
                        *out_addr = (uint16_t)strtoul(val_str, NULL, 10);
                    }
                    if (out_meta) *out_meta = ga700_find_param_by_addr(*out_addr);
                    free(qry);
                    return true;
                }
                // Check 'param' or 'code' (e.g. A1-00)
                if (httpd_query_key_value(qry, "param", val_str, sizeof(val_str)) == ESP_OK ||
                    httpd_query_key_value(qry, "code", val_str, sizeof(val_str)) == ESP_OK) {
                    const ga700_param_meta_t *meta = ga700_find_param_by_code(val_str);
                    if (meta != NULL) {
                        *out_addr = meta->address;
                        if (out_meta) *out_meta = meta;
                        free(qry);
                        return true;
                    }
                }
            }
            free(qry);
        }
    }
    return false;
}

/**
 * GET /api/param?addr=0x0100 (or ?code=A1-00)
 */
static esp_err_t api_get_param_handler(httpd_req_t *req)
{
    set_cors_headers(req);
    httpd_resp_set_type(req, "application/json");

    uint16_t reg_addr = 0;
    const ga700_param_meta_t *meta = NULL;

    if (!parse_param_address(req, &reg_addr, &meta)) {
        httpd_resp_set_status(req, "400 Bad Request");
        const char *err = "{\"status\":\"error\",\"message\":\"Missing or invalid 'addr' or 'code' parameter\"}";
        return httpd_resp_send(req, err, HTTPD_RESP_USE_STRLEN);
    }

    uint16_t reg_val = 0;
    esp_err_t err = ga700_read_holding_register(reg_addr, &reg_val);

    char resp[350];
    if (err == ESP_OK) {
        snprintf(resp, sizeof(resp),
            "{\"status\":\"ok\",\"code\":\"%s\",\"name\":\"%s\",\"address\":\"0x%04X\",\"address_dec\":%u,\"value\":%u,\"hex_value\":\"0x%04X\"}",
            meta ? meta->code : "UNKNOWN",
            meta ? meta->name : "Custom Register",
            reg_addr, reg_addr,
            reg_val, reg_val);
        return httpd_resp_send(req, resp, HTTPD_RESP_USE_STRLEN);
    } else {
        snprintf(resp, sizeof(resp),
            "{\"status\":\"error\",\"address\":\"0x%04X\",\"error\":\"%s\",\"message\":\"Modbus read failed\"}",
            reg_addr, esp_err_to_name(err));
        httpd_resp_set_status(req, "500 Internal Server Error");
        return httpd_resp_send(req, resp, HTTPD_RESP_USE_STRLEN);
    }
}

/**
 * POST /api/param
 * Supports JSON: {"address":"0x0100", "value": 1}
 * or Query: ?addr=0x0100&val=1
 */
static esp_err_t api_post_param_handler(httpd_req_t *req)
{
    set_cors_headers(req);
    httpd_resp_set_type(req, "application/json");

    uint16_t reg_addr = 0;
    uint16_t reg_val = 0;
    bool has_addr = false;
    bool has_val = false;

    // 1. Try URL Query
    size_t qry_len = httpd_req_get_url_query_len(req);
    if (qry_len > 0) {
        char *qry = malloc(qry_len + 1);
        if (qry && httpd_req_get_url_query_str(req, qry, qry_len + 1) == ESP_OK) {
            char val_str[64];
            if (httpd_query_key_value(qry, "addr", val_str, sizeof(val_str)) == ESP_OK ||
                httpd_query_key_value(qry, "address", val_str, sizeof(val_str)) == ESP_OK) {
                reg_addr = (val_str[0] == '0' && (val_str[1] == 'x' || val_str[1] == 'X'))
                    ? (uint16_t)strtoul(val_str, NULL, 16)
                    : (uint16_t)strtoul(val_str, NULL, 10);
                has_addr = true;
            }
            if (httpd_query_key_value(qry, "val", val_str, sizeof(val_str)) == ESP_OK ||
                httpd_query_key_value(qry, "value", val_str, sizeof(val_str)) == ESP_OK) {
                reg_val = (val_str[0] == '0' && (val_str[1] == 'x' || val_str[1] == 'X'))
                    ? (uint16_t)strtoul(val_str, NULL, 16)
                    : (uint16_t)strtoul(val_str, NULL, 10);
                has_val = true;
            }
            free(qry);
        }
    }

    // 2. Try JSON Body if not found in query
    if (!has_addr || !has_val) {
        int total_len = req->content_len;
        if (total_len > 0 && total_len < 1024) {
            char body[256];
            int received = httpd_req_recv(req, body, sizeof(body) - 1);
            if (received > 0) {
                body[received] = '\0';
                char *addr_pos = strstr(body, "\"address\"");
                if (!addr_pos) addr_pos = strstr(body, "\"addr\"");
                if (addr_pos) {
                    char *col = strchr(addr_pos, ':');
                    if (col) {
                        while (*col == ':' || *col == ' ' || *col == '"') col++;
                        if (strncmp(col, "0x", 2) == 0 || strncmp(col, "0X", 2) == 0) {
                            reg_addr = (uint16_t)strtoul(col, NULL, 16);
                        } else {
                            reg_addr = (uint16_t)strtoul(col, NULL, 10);
                        }
                        has_addr = true;
                    }
                }

                char *val_pos = strstr(body, "\"value\"");
                if (!val_pos) val_pos = strstr(body, "\"val\"");
                if (val_pos) {
                    char *col = strchr(val_pos, ':');
                    if (col) {
                        while (*col == ':' || *col == ' ' || *col == '"') col++;
                        if (strncmp(col, "0x", 2) == 0 || strncmp(col, "0X", 2) == 0) {
                            reg_val = (uint16_t)strtoul(col, NULL, 16);
                        } else {
                            reg_val = (uint16_t)strtoul(col, NULL, 10);
                        }
                        has_val = true;
                    }
                }
            }
        }
    }

    if (!has_addr || !has_val) {
        httpd_resp_set_status(req, "400 Bad Request");
        const char *err = "{\"status\":\"error\",\"message\":\"Missing 'address' or 'value' in request\"}";
        return httpd_resp_send(req, err, HTTPD_RESP_USE_STRLEN);
    }

    ESP_LOGI(TAG, "Writing register 0x%04X = %u (0x%04X)", reg_addr, reg_val, reg_val);
    esp_err_t err = ga700_write_single_register(reg_addr, reg_val);

    const ga700_param_meta_t *meta = ga700_find_param_by_addr(reg_addr);
    char resp[350];
    if (err == ESP_OK) {
        snprintf(resp, sizeof(resp),
            "{\"status\":\"ok\",\"code\":\"%s\",\"name\":\"%s\",\"address\":\"0x%04X\",\"address_dec\":%u,\"written_value\":%u,\"hex_value\":\"0x%04X\"}",
            meta ? meta->code : "UNKNOWN",
            meta ? meta->name : "Custom Register",
            reg_addr, reg_addr,
            reg_val, reg_val);
        return httpd_resp_send(req, resp, HTTPD_RESP_USE_STRLEN);
    } else {
        snprintf(resp, sizeof(resp),
            "{\"status\":\"error\",\"address\":\"0x%04X\",\"error\":\"%s\",\"message\":\"Modbus write failed\"}",
            reg_addr, esp_err_to_name(err));
        httpd_resp_set_status(req, "500 Internal Server Error");
        return httpd_resp_send(req, resp, HTTPD_RESP_USE_STRLEN);
    }
}

esp_err_t register_param_api_endpoints(httpd_handle_t server)
{
    if (server == NULL) return ESP_ERR_INVALID_ARG;

    // OPTIONS /api/param
    httpd_uri_t uri_opt = {
        .uri      = "/api/param",
        .method   = HTTP_OPTIONS,
        .handler  = param_options_handler,
        .user_ctx = NULL
    };
    httpd_register_uri_handler(server, &uri_opt);

    // GET /api/param
    httpd_uri_t uri_get = {
        .uri      = "/api/param",
        .method   = HTTP_GET,
        .handler  = api_get_param_handler,
        .user_ctx = NULL
    };
    httpd_register_uri_handler(server, &uri_get);

    // POST /api/param
    httpd_uri_t uri_post = {
        .uri      = "/api/param",
        .method   = HTTP_POST,
        .handler  = api_post_param_handler,
        .user_ctx = NULL
    };
    httpd_register_uri_handler(server, &uri_post);

    ESP_LOGI(TAG, "Parameter REST API Endpoints registered (/api/param GET/POST/OPTIONS)");
    return ESP_OK;
}
