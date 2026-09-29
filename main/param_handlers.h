#ifndef PARAM_HANDLERS_H
#define PARAM_HANDLERS_H

#include "esp_err.h"
#include "esp_http_server.h"

#ifdef __cplusplus
extern "C" {
#endif

esp_err_t register_param_api_endpoints(httpd_handle_t server);

#ifdef __cplusplus
}
#endif

#endif // PARAM_HANDLERS_H
