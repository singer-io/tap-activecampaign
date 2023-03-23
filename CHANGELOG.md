# Changelog

## 1.0.0
  * Changes in doc links in README [#33](https://github.com/singer-io/tap-activecampaign/pull/33)
  * Fix existing integration tests and add interrupted sync test [#35](https://github.com/singer-io/tap-activecampaign/pull/35)
  * Load data with same datetime as last bookmark [#34](https://github.com/singer-io/tap-activecampaign/pull/34)
  * Handle ChunkEncodingError & JSONDecodeError [#36](https://github.com/singer-io/tap-activecampaign/pull/36)
  * Fix Nonetype error for no records [#37](https://github.com/singer-io/tap-activecampaign/pull/37)
  * Add phone to list of supported fields [#26](https://github.com/singer-io/tap-activecampaign/pull/26)
  * Add string type for forms style.button.padding [#28](https://github.com/singer-io/tap-activecampaign/pull/28)

## 0.3.3
  * Added after param for activities stream [#24](https://github.com/singer-io/tap-activecampaign/pull/24)

## 0.3.2
  * Fix the transformation error of forms stream [#22](https://github.com/singer-io/tap-activecampaign/pull/22)

## 0.3.1
  * Breakdown of Sync method for better readability of code[#16](https://github.com/singer-io/tap-activecampaign/pull/16)

## 0.3.0
  * Refactor code to class based [#8](https://github.com/singer-io/tap-activecampaign/pull/8)
  * Update all schemas [#10](https://github.com/singer-io/tap-activecampaign/pull/10)
  * Refactor Error Handling [#8] (https://github.com/singer-io/tap-activecampaign/pull/8)
  * Check best practices and make replication key with automatic inclusion [#11](https://github.com/singer-io/tap-activecampaign/pull/11)
  * Updated Documentation
  * Official Beta Release

## 0.0.6
  * Fixed issue where a Connection Reset Error was not being retried [#4](https://github.com/singer-io/tap-activecampaign/pull/4)

## 0.0.5
  * Fixing issue that was causing duplication of records to be emitted and updated stream with correct replication key and created at timestamp. [#5](https://github.com/singer-io/tap-activecampaign/pull/5)

## 0.0.4
  * Fix response message being truncated. Change `client.py` to request `stream=True` and error message to include `response.content`. Decrease `sync.py` batch size to `pg_size = 100`.

## 0.0.3
  * Upgrade `singer-python` and `requests` libraries. Reduce batch sizes. Better error logging in `client.py` to log `unterminated string` error results.

## 0.0.2
  * Fix bookmarking. Data is not sorted; need to write bookmark after ALL pages.

## 0.0.1
  * Initial commit
