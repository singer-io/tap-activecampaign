# Changelog

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
