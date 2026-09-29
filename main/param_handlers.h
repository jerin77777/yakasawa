#ifndef PARAM_HANDLERS_H
#define PARAM_HANDLERS_H

#include "esp_err.h"
#include "esp_http_server.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Register parameter REST API endpoints to ESP32 HTTP Server:
 * - GET  /api/param?addr=0x0100 (Read register)
 * - POST /api/param (Write register: {"address":"0x0100","value":1})
 * - OPTIONS /api/param (CORS Preflight)
 * - GET  /params (Embedded Web Parameter Explorer)
 */
esp_err_t register_param_api_endpoints(httpd_handle_t server);

#ifdef __cplusplus
}
#endif

#endif // PARAM_HANDLERS_H
