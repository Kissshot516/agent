# 支付失败排查手册

当支付失败率升高时，优先检查以下证据：

1. 支付服务错误日志中是否出现 `RedisTimeoutError`、`ConnectionPoolExhausted` 或支付网关超时。
2. `payment-service` 的 P95 延迟是否明显高于基线。
3. Redis 连接数是否达到 `max_clients` 上限。
4. 数据库慢查询是否同步升高。

如果 Redis 连接数达到上限且错误日志包含 Redis 超时，优先判断为 Redis 连接池耗尽。建议先临时扩容连接池或 Redis 实例，再检查调用方是否存在连接泄漏。
