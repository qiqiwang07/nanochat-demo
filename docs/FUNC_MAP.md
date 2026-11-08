# 函数调用关系表

> 本文档由 `tools/gen_func_map.py` 自动生成，**请勿手工编辑**。
> 重新生成：`python tools/gen_func_map.py`

## 总览

| 指标 | 数值 |
|---|---|
| 文件数 | 48 |
| 函数总数 | 556 |
| 调用关系统计 | 2801 条 |

| 文件 | 函数数 |
|---|---|
| `deploy/bench_7b.py` | 1 |
| `deploy/bench_server.py` | 1 |
| `deploy/check_server.py` | 1 |
| `deploy/deploy_app_to_server.py` | 1 |
| `deploy/package/server/server_cloud.py` | 8 |
| `deploy/package/worker.py` | 16 |
| `deploy/server_cloud.py` | 8 |
| `deploy/setup_ai_start.py` | 1 |
| `deploy/show_nginx.py` | 1 |
| `deploy/stage/agent_r1.py` | 12 |
| `deploy/stage/serve_r1.py` | 15 |
| `deploy/stage/worker.py` | 16 |
| `deploy/start_7b.py` | 1 |
| `deploy/test_domain.py` | 1 |
| `deploy/test_public.py` | 1 |
| `deploy/upload_7b.py` | 1 |
| `deploy/upload_7b_resume.py` | 2 |
| `deploy/upload_shards.py` | 2 |
| `deploy/watch_server.py` | 2 |
| `deploy/worker.py` | 10 |
| `src/ai.c` | 55 |
| `src/gui.c` | 73 |
| `src/nanogpt.c` | 48 |
| `src/nanogpt_dbl.c` | 24 |
| `src/qwen.c` | 19 |
| `src/server.c` | 71 |
| `src/solver.c` | 28 |
| `src/test_answer.c` | 58 |
| `tools/agent_r1.py` | 12 |
| `tools/build_olympiad_corpus.py` | 1 |
| `tools/build_olympiad_index.py` | 1 |
| `tools/download_model.py` | 1 |
| `tools/drive_gui.c` | 3 |
| `tools/extract_books.py` | 4 |
| `tools/fix_olympiad_corpus.py` | 1 |
| `tools/fix_stream_nonthinking.py` | 1 |
| `tools/gen_func_map.py` | 6 |
| `tools/gui_part.c` | 10 |
| `tools/local_proxy.py` | 5 |
| `tools/make_gui.py` | 2 |
| `tools/make_server.py` | 2 |
| `tools/make_test.py` | 2 |
| `tools/merge_ai.py` | 1 |
| `tools/patch_verbose.py` | 1 |
| `tools/serve_r1.py` | 17 |
| `tools/server_part.c` | 7 |
| `tools/test_main.c` | 1 |
| `tools/train_lora.py` | 1 |

---

## `deploy/bench_7b.py`

### `ask()`

**调用：** `Request`、`decode`、`dumps`、`encode`、`get`、`loads`、`read`、`strip`、`time`、`urlopen`

**被调用：** 无（入口函数或未被引用）

---

## `deploy/bench_server.py`

### `run()`

**调用：** `decode`、`exec_command`、`read`、`strip`

**被调用：** `deploy/stage/agent_r1.py :: run_verify`、`tools/agent_r1.py :: run_verify`

---

## `deploy/check_server.py`

### `run()`

**调用：** `decode`、`exec_command`、`read`、`strip`

**被调用：** `deploy/stage/agent_r1.py :: run_verify`、`tools/agent_r1.py :: run_verify`

---

## `deploy/deploy_app_to_server.py`

### `run()`

**调用：** `decode`、`exec_command`、`read`、`strip`

**被调用：** `deploy/stage/agent_r1.py :: run_verify`、`tools/agent_r1.py :: run_verify`

---

## `deploy/package/server/server_cloud.py`

### `_json()`

**调用：** `dumps`、`encode`、`end_headers`、`len`、`send_header`、`send_response`、`str`、`write`

**被调用：** `deploy/package/server/server_cloud.py :: do_GET`、`deploy/package/server/server_cloud.py :: do_POST`、`deploy/server_cloud.py :: do_GET`、`deploy/server_cloud.py :: do_POST`

### `_page()`

**调用：** `end_headers`、`join`、`len`、`open`、`read`、`send_header`、`send_response`、`str`、`write`

**被调用：** `deploy/package/server/server_cloud.py :: do_GET`、`deploy/server_cloud.py :: do_GET`

### `cleanup()`

**调用：** `items`、`pop`、`time`

**被调用：** `deploy/package/server/server_cloud.py :: do_GET`、`deploy/server_cloud.py :: do_GET`

### `do_GET()`

**调用：** `_json`、`_page`、`cleanup`、`end_headers`、`get`、`len`、`parse_qs`、`send_header`、`send_response`、`urlparse`

**被调用：** 无（入口函数或未被引用）

### `do_POST()`

**调用：** `_json`、`append`、`dumps`、`encode`、`end_headers`、`flush`、`get`、`int`、`len`、`loads`、`new_task`、`print`、`read`、`send_header`、`send_response`、`sleep`、`strip`、`time`、`urlparse`、`write`

**被调用：** 无（入口函数或未被引用）

### `log_message()`

**调用：** `print`、`strftime`

**被调用：** 无（入口函数或未被引用）

### `main()`

**调用：** `ThreadingHTTPServer`、`print`、`serve_forever`

**被调用：** 无（入口函数或未被引用）

### `new_task()`

**调用：** `put`、`time`、`uuid4`

**被调用：** `deploy/package/server/server_cloud.py :: do_POST`、`deploy/server_cloud.py :: do_POST`

---

## `deploy/package/worker.py`

### `_grams()`

**调用：** `isspace`、`join`、`len`、`range`

**被调用：** `deploy/package/worker.py :: build_index`、`deploy/package/worker.py :: retrieve`、`deploy/stage/serve_r1.py :: build_index`、`deploy/stage/serve_r1.py :: retrieve`、`deploy/stage/worker.py :: build_index`、`deploy/stage/worker.py :: retrieve`、`deploy/worker.py :: build_index`、`deploy/worker.py :: retrieve`、`tools/serve_r1.py :: build_index`、`tools/serve_r1.py :: load_olympiad`、`tools/serve_r1.py :: retrieve`、`tools/serve_r1.py :: retrieve_olympiad`

### `answer()`

**调用：** `Request`、`decode`、`dumps`、`encode`、`get`、`int`、`join`、`len`、`loads`、`log`、`lstrip`、`retrieve`、`rstrip`、`send_chunk`、`send_done`、`split`、`startswith`、`strip`、`time`、`urlopen`

**被调用：** `deploy/package/worker.py :: main`、`deploy/stage/worker.py :: main`、`deploy/worker.py :: main`

### `build_index()`

**调用：** `_grams`、`append`、`exists`、`len`、`log`、`max`、`open`、`range`、`read`、`strip`

**被调用：** `deploy/package/worker.py :: main`、`deploy/stage/serve_r1.py :: main`、`deploy/stage/worker.py :: main`、`deploy/worker.py :: main`、`src/solver.c :: main`、`tools/serve_r1.py :: main`

### `ensure_model()`

**调用：** `Popen`、`find_llama`、`find_model`、`get`、`join`、`log`、`model_alive`、`range`、`sleep`、`str`、`urlparse`

**被调用：** `deploy/package/worker.py :: main`、`deploy/stage/worker.py :: main`

### `find_llama()`

**调用：** `append`、`exists`、`get`、`join`、`which`

**被调用：** `deploy/package/worker.py :: ensure_model`、`deploy/stage/worker.py :: ensure_model`

### `find_model()`

**调用：** `endswith`、`exists`、`get`、`join`、`listdir`、`lower`

**被调用：** `deploy/package/worker.py :: ensure_model`、`deploy/stage/worker.py :: ensure_model`

### `load_config()`

**调用：** `dict`、`exists`、`get`、`load`、`log`、`open`、`update`

**被调用：** `deploy/package/worker.py :: main`、`deploy/stage/worker.py :: main`

### `log()`

**调用：** `print`、`strftime`

**被调用：** `deploy/package/worker.py :: answer`、`deploy/package/worker.py :: build_index`、`deploy/package/worker.py :: ensure_model`、`deploy/package/worker.py :: load_config`、`deploy/package/worker.py :: main`、`deploy/package/worker.py :: poll`、`deploy/package/worker.py :: send_chunk`、`deploy/package/worker.py :: send_done`、`deploy/stage/worker.py :: answer`、`deploy/stage/worker.py :: build_index`、`deploy/stage/worker.py :: ensure_model`、`deploy/stage/worker.py :: load_config`

### `main()`

**调用：** `ArgumentParser`、`add_argument`、`answer`、`build_index`、`ensure_model`、`get`、`join`、`load_config`、`log`、`parse_args`、`poll`、`save_default_config`、`send_chunk`、`send_done`、`sleep`

**被调用：** 无（入口函数或未被引用）

### `model_alive()`

**调用：** `Request`、`rstrip`、`urlopen`

**被调用：** `deploy/package/worker.py :: ensure_model`、`deploy/stage/worker.py :: ensure_model`

### `poll()`

**调用：** `loads`、`log`、`relay_request`

**被调用：** `deploy/package/worker.py :: main`、`deploy/stage/worker.py :: main`、`deploy/worker.py :: main`

### `relay_request()`

**调用：** `HTTPConnection`、`close`、`dumps`、`encode`、`get`、`getresponse`、`read`、`request`、`urlparse`

**被调用：** `deploy/package/worker.py :: poll`、`deploy/package/worker.py :: send_chunk`、`deploy/package/worker.py :: send_done`、`deploy/stage/worker.py :: poll`、`deploy/stage/worker.py :: send_chunk`、`deploy/stage/worker.py :: send_done`

### `retrieve()`

**调用：** `_grams`、`append`、`enumerate`、`len`、`sort`

**被调用：** `deploy/package/worker.py :: answer`、`deploy/stage/serve_r1.py :: do_POST`、`deploy/stage/worker.py :: answer`、`deploy/worker.py :: answer`、`tools/serve_r1.py :: do_POST`

### `save_default_config()`

**调用：** `dump`、`exists`、`open`

**被调用：** `deploy/package/worker.py :: main`、`deploy/stage/worker.py :: main`

### `send_chunk()`

**调用：** `log`、`relay_request`

**被调用：** `deploy/package/worker.py :: answer`、`deploy/package/worker.py :: main`、`deploy/stage/worker.py :: answer`、`deploy/stage/worker.py :: main`、`deploy/worker.py :: answer`、`deploy/worker.py :: main`

### `send_done()`

**调用：** `log`、`relay_request`

**被调用：** `deploy/package/worker.py :: answer`、`deploy/package/worker.py :: main`、`deploy/stage/worker.py :: answer`、`deploy/stage/worker.py :: main`、`deploy/worker.py :: answer`、`deploy/worker.py :: main`

---

## `deploy/server_cloud.py`

### `_json()`

**调用：** `dumps`、`encode`、`end_headers`、`len`、`send_header`、`send_response`、`str`、`write`

**被调用：** `deploy/package/server/server_cloud.py :: do_GET`、`deploy/package/server/server_cloud.py :: do_POST`、`deploy/server_cloud.py :: do_GET`、`deploy/server_cloud.py :: do_POST`

### `_page()`

**调用：** `end_headers`、`join`、`len`、`open`、`read`、`send_header`、`send_response`、`str`、`write`

**被调用：** `deploy/package/server/server_cloud.py :: do_GET`、`deploy/server_cloud.py :: do_GET`

### `cleanup()`

**调用：** `items`、`pop`、`time`

**被调用：** `deploy/package/server/server_cloud.py :: do_GET`、`deploy/server_cloud.py :: do_GET`

### `do_GET()`

**调用：** `_json`、`_page`、`basename`、`cleanup`、`end_headers`、`endswith`、`exists`、`get`、`getsize`、`int`、`isfile`、`join`、`len`、`min`、`open`、`parse_qs`、`partition`、`print`、`read`、`seek`、`send_header`、`send_response`、`split`、`startswith`、`str`、`strip`、`urlparse`、`write`

**被调用：** 无（入口函数或未被引用）

### `do_POST()`

**调用：** `_json`、`append`、`dumps`、`encode`、`end_headers`、`flush`、`get`、`int`、`len`、`loads`、`new_task`、`print`、`read`、`send_header`、`send_response`、`sleep`、`strip`、`time`、`urlparse`、`write`

**被调用：** 无（入口函数或未被引用）

### `log_message()`

**调用：** `print`、`strftime`

**被调用：** 无（入口函数或未被引用）

### `main()`

**调用：** `ThreadingHTTPServer`、`print`、`serve_forever`

**被调用：** 无（入口函数或未被引用）

### `new_task()`

**调用：** `put`、`time`、`uuid4`

**被调用：** `deploy/package/server/server_cloud.py :: do_POST`、`deploy/server_cloud.py :: do_POST`

---

## `deploy/setup_ai_start.py`

### `run()`

**调用：** `decode`、`exec_command`、`read`、`strip`

**被调用：** `deploy/stage/agent_r1.py :: run_verify`、`tools/agent_r1.py :: run_verify`

---

## `deploy/show_nginx.py`

### `run()`

**调用：** `decode`、`exec_command`、`read`、`strip`

**被调用：** `deploy/stage/agent_r1.py :: run_verify`、`tools/agent_r1.py :: run_verify`

---

## `deploy/stage/agent_r1.py`

### `_send()`

**调用：** `end_headers`、`len`、`send_header`、`send_response`、`str`、`write`

**被调用：** `deploy/stage/agent_r1.py :: do_GET`、`deploy/stage/agent_r1.py :: do_POST`、`deploy/stage/serve_r1.py :: do_GET`、`deploy/stage/serve_r1.py :: do_POST`、`tools/agent_r1.py :: do_GET`、`tools/agent_r1.py :: do_POST`、`tools/serve_r1.py :: do_GET`、`tools/serve_r1.py :: do_POST`

### `do_GET()`

**调用：** `_send`、`abspath`、`dirname`、`dumps`、`encode`、`join`、`open`、`read`

**被调用：** 无（入口函数或未被引用）

### `do_POST()`

**调用：** `Lock`、`_send`、`dumps`、`emit`、`encode`、`end_headers`、`flush`、`get`、`handle_task`、`int`、`loads`、`read`、`send_header`、`send_response`、`strip`、`write`

**被调用：** 无（入口函数或未被引用）

### `emit()`

**调用：** `dumps`、`encode`、`flush`、`write`

**被调用：** `deploy/stage/agent_r1.py :: do_POST`、`deploy/stage/agent_r1.py :: handle_task`、`deploy/stage/agent_r1.py :: pick_file`、`deploy/stage/serve_r1.py :: do_POST`、`src/ai.c :: try_rules`、`src/gui.c :: try_rules`、`src/server.c :: try_rules`、`src/solver.c :: try_rules`、`src/test_answer.c :: try_rules`、`tools/agent_r1.py :: do_POST`、`tools/agent_r1.py :: handle_task`、`tools/agent_r1.py :: pick_file`

### `handle_task()`

**调用：** `basename`、`emit`、`encode`、`len`、`llama_chat`、`open`、`pick_file`、`read`、`replace`、`rsplit`、`run_verify`、`safe_path`、`strip`、`strip_fence`、`write`

**被调用：** `deploy/stage/agent_r1.py :: do_POST`、`tools/agent_r1.py :: do_POST`

### `llama_chat()`

**调用：** `Request`、`decode`、`dumps`、`encode`、`get`、`loads`、`read`、`rsplit`、`strip`、`urlopen`

**被调用：** `deploy/stage/agent_r1.py :: handle_task`、`deploy/stage/agent_r1.py :: pick_file`、`tools/agent_r1.py :: handle_task`、`tools/agent_r1.py :: pick_file`

### `log_message()`

**调用：** 无（叶子函数）

**被调用：** 无（入口函数或未被引用）

### `main()`

**调用：** `ArgumentParser`、`ThreadingHTTPServer`、`abspath`、`add_argument`、`makedirs`、`parse_args`、`print`、`serve_forever`

**被调用：** 无（入口函数或未被引用）

### `pick_file()`

**调用：** `emit`、`isfile`、`join`、`listdir`、`llama_chat`、`replace`、`sorted`、`strip`

**被调用：** `deploy/stage/agent_r1.py :: handle_task`、`tools/agent_r1.py :: handle_task`

### `run_verify()`

**调用：** `lower`、`run`、`splitext`

**被调用：** `deploy/stage/agent_r1.py :: handle_task`、`tools/agent_r1.py :: handle_task`

### `safe_path()`

**调用：** `ValueError`、`abspath`、`join`、`lstrip`、`replace`、`startswith`

**被调用：** `deploy/stage/agent_r1.py :: handle_task`、`tools/agent_r1.py :: handle_task`

### `strip_fence()`

**调用：** `any`、`append`、`group`、`join`、`rstrip`、`search`、`splitlines`、`startswith`、`strip`

**被调用：** `deploy/stage/agent_r1.py :: handle_task`、`tools/agent_r1.py :: handle_task`

---

## `deploy/stage/serve_r1.py`

### `_grams()`

**调用：** `isspace`、`join`、`len`、`range`

**被调用：** `deploy/package/worker.py :: build_index`、`deploy/package/worker.py :: retrieve`、`deploy/stage/serve_r1.py :: build_index`、`deploy/stage/serve_r1.py :: retrieve`、`deploy/stage/worker.py :: build_index`、`deploy/stage/worker.py :: retrieve`、`deploy/worker.py :: build_index`、`deploy/worker.py :: retrieve`、`tools/serve_r1.py :: build_index`、`tools/serve_r1.py :: load_olympiad`、`tools/serve_r1.py :: retrieve`、`tools/serve_r1.py :: retrieve_olympiad`

### `_send()`

**调用：** `end_headers`、`len`、`send_header`、`send_response`、`str`、`write`

**被调用：** `deploy/stage/agent_r1.py :: do_GET`、`deploy/stage/agent_r1.py :: do_POST`、`deploy/stage/serve_r1.py :: do_GET`、`deploy/stage/serve_r1.py :: do_POST`、`tools/agent_r1.py :: do_GET`、`tools/agent_r1.py :: do_POST`、`tools/serve_r1.py :: do_GET`、`tools/serve_r1.py :: do_POST`

### `build_index()`

**调用：** `_grams`、`append`、`exists`、`len`、`max`、`open`、`print`、`range`、`read`、`strip`、`time`

**被调用：** `deploy/package/worker.py :: main`、`deploy/stage/serve_r1.py :: main`、`deploy/stage/worker.py :: main`、`deploy/worker.py :: main`、`src/solver.c :: main`、`tools/serve_r1.py :: main`

### `do_GET()`

**调用：** `_send`、`dumps`、`encode`、`get`、`items`、`join`、`open`、`parse_qs`、`read`、`sort`、`urlparse`

**被调用：** 无（入口函数或未被引用）

### `do_POST()`

**调用：** `_send`、`append`、`dumps`、`emit`、`encode`、`end_headers`、`flush`、`get`、`int`、`join`、`len`、`list`、`loads`、`new_sid`、`read`、`retrieve`、`save_session`、`send_header`、`send_response`、`stream_llama`、`strip`、`strip_refs`、`urlparse`、`write`

**被调用：** 无（入口函数或未被引用）

### `emit()`

**调用：** `dumps`、`encode`、`flush`、`write`

**被调用：** `deploy/stage/agent_r1.py :: do_POST`、`deploy/stage/agent_r1.py :: handle_task`、`deploy/stage/agent_r1.py :: pick_file`、`deploy/stage/serve_r1.py :: do_POST`、`src/ai.c :: try_rules`、`src/gui.c :: try_rules`、`src/server.c :: try_rules`、`src/solver.c :: try_rules`、`src/test_answer.c :: try_rules`、`tools/agent_r1.py :: do_POST`、`tools/agent_r1.py :: handle_task`、`tools/agent_r1.py :: pick_file`

### `load_sessions()`

**调用：** `endswith`、`join`、`listdir`、`load`、`makedirs`、`open`

**被调用：** `deploy/stage/serve_r1.py :: main`、`src/server.c :: main`、`tools/serve_r1.py :: main`、`tools/server_part.c :: main`

### `log_message()`

**调用：** 无（叶子函数）

**被调用：** 无（入口函数或未被引用）

### `main()`

**调用：** `ArgumentParser`、`ThreadingHTTPServer`、`add_argument`、`build_index`、`load_sessions`、`parse_args`、`print`、`serve_forever`

**被调用：** 无（入口函数或未被引用）

### `new_sid()`

**调用：** `int`、`time`

**被调用：** `deploy/stage/serve_r1.py :: do_POST`、`tools/serve_r1.py :: do_POST`

### `retrieve()`

**调用：** `_grams`、`append`、`enumerate`、`len`、`sort`

**被调用：** `deploy/package/worker.py :: answer`、`deploy/stage/serve_r1.py :: do_POST`、`deploy/stage/worker.py :: answer`、`deploy/worker.py :: answer`、`tools/serve_r1.py :: do_POST`

### `save_session()`

**调用：** `dump`、`join`、`makedirs`、`open`

**被调用：** `deploy/stage/serve_r1.py :: do_POST`、`tools/serve_r1.py :: do_POST`

### `stream_llama()`

**调用：** `Request`、`decode`、`dumps`、`encode`、`get`、`int`、`len`、`loads`、`lstrip`、`print`、`split`、`startswith`、`strip`、`time`、`urlopen`

**被调用：** `deploy/stage/serve_r1.py :: do_POST`、`tools/serve_r1.py :: do_POST`

### `strip_refs()`

**调用：** `strip`、`sub`

**被调用：** `deploy/stage/serve_r1.py :: do_POST`、`tools/serve_r1.py :: do_POST`

### `strip_thinking()`

**调用：** `rsplit`、`strip`

**被调用：** 无（入口函数或未被引用）

---

## `deploy/stage/worker.py`

### `_grams()`

**调用：** `isspace`、`join`、`len`、`range`

**被调用：** `deploy/package/worker.py :: build_index`、`deploy/package/worker.py :: retrieve`、`deploy/stage/serve_r1.py :: build_index`、`deploy/stage/serve_r1.py :: retrieve`、`deploy/stage/worker.py :: build_index`、`deploy/stage/worker.py :: retrieve`、`deploy/worker.py :: build_index`、`deploy/worker.py :: retrieve`、`tools/serve_r1.py :: build_index`、`tools/serve_r1.py :: load_olympiad`、`tools/serve_r1.py :: retrieve`、`tools/serve_r1.py :: retrieve_olympiad`

### `answer()`

**调用：** `Request`、`decode`、`dumps`、`encode`、`get`、`int`、`join`、`len`、`loads`、`log`、`lstrip`、`retrieve`、`rstrip`、`send_chunk`、`send_done`、`split`、`startswith`、`strip`、`time`、`urlopen`

**被调用：** `deploy/package/worker.py :: main`、`deploy/stage/worker.py :: main`、`deploy/worker.py :: main`

### `build_index()`

**调用：** `_grams`、`append`、`exists`、`len`、`log`、`max`、`open`、`range`、`read`、`strip`

**被调用：** `deploy/package/worker.py :: main`、`deploy/stage/serve_r1.py :: main`、`deploy/stage/worker.py :: main`、`deploy/worker.py :: main`、`src/solver.c :: main`、`tools/serve_r1.py :: main`

### `ensure_model()`

**调用：** `Popen`、`find_llama`、`find_model`、`get`、`join`、`log`、`model_alive`、`range`、`sleep`、`str`、`urlparse`

**被调用：** `deploy/package/worker.py :: main`、`deploy/stage/worker.py :: main`

### `find_llama()`

**调用：** `append`、`exists`、`get`、`join`、`which`

**被调用：** `deploy/package/worker.py :: ensure_model`、`deploy/stage/worker.py :: ensure_model`

### `find_model()`

**调用：** `endswith`、`exists`、`get`、`join`、`listdir`、`lower`

**被调用：** `deploy/package/worker.py :: ensure_model`、`deploy/stage/worker.py :: ensure_model`

### `load_config()`

**调用：** `dict`、`exists`、`get`、`load`、`log`、`open`、`update`

**被调用：** `deploy/package/worker.py :: main`、`deploy/stage/worker.py :: main`

### `log()`

**调用：** `print`、`strftime`

**被调用：** `deploy/package/worker.py :: answer`、`deploy/package/worker.py :: build_index`、`deploy/package/worker.py :: ensure_model`、`deploy/package/worker.py :: load_config`、`deploy/package/worker.py :: main`、`deploy/package/worker.py :: poll`、`deploy/package/worker.py :: send_chunk`、`deploy/package/worker.py :: send_done`、`deploy/stage/worker.py :: answer`、`deploy/stage/worker.py :: build_index`、`deploy/stage/worker.py :: ensure_model`、`deploy/stage/worker.py :: load_config`

### `main()`

**调用：** `ArgumentParser`、`add_argument`、`answer`、`build_index`、`ensure_model`、`get`、`join`、`load_config`、`log`、`parse_args`、`poll`、`save_default_config`、`send_chunk`、`send_done`、`sleep`

**被调用：** 无（入口函数或未被引用）

### `model_alive()`

**调用：** `Request`、`rstrip`、`urlopen`

**被调用：** `deploy/package/worker.py :: ensure_model`、`deploy/stage/worker.py :: ensure_model`

### `poll()`

**调用：** `loads`、`log`、`relay_request`

**被调用：** `deploy/package/worker.py :: main`、`deploy/stage/worker.py :: main`、`deploy/worker.py :: main`

### `relay_request()`

**调用：** `HTTPConnection`、`close`、`dumps`、`encode`、`get`、`getresponse`、`read`、`request`、`urlparse`

**被调用：** `deploy/package/worker.py :: poll`、`deploy/package/worker.py :: send_chunk`、`deploy/package/worker.py :: send_done`、`deploy/stage/worker.py :: poll`、`deploy/stage/worker.py :: send_chunk`、`deploy/stage/worker.py :: send_done`

### `retrieve()`

**调用：** `_grams`、`append`、`enumerate`、`len`、`sort`

**被调用：** `deploy/package/worker.py :: answer`、`deploy/stage/serve_r1.py :: do_POST`、`deploy/stage/worker.py :: answer`、`deploy/worker.py :: answer`、`tools/serve_r1.py :: do_POST`

### `save_default_config()`

**调用：** `dump`、`exists`、`open`

**被调用：** `deploy/package/worker.py :: main`、`deploy/stage/worker.py :: main`

### `send_chunk()`

**调用：** `log`、`relay_request`

**被调用：** `deploy/package/worker.py :: answer`、`deploy/package/worker.py :: main`、`deploy/stage/worker.py :: answer`、`deploy/stage/worker.py :: main`、`deploy/worker.py :: answer`、`deploy/worker.py :: main`

### `send_done()`

**调用：** `log`、`relay_request`

**被调用：** `deploy/package/worker.py :: answer`、`deploy/package/worker.py :: main`、`deploy/stage/worker.py :: answer`、`deploy/stage/worker.py :: main`、`deploy/worker.py :: answer`、`deploy/worker.py :: main`

---

## `deploy/start_7b.py`

### `run()`

**调用：** `decode`、`exec_command`、`read`、`strip`

**被调用：** `deploy/stage/agent_r1.py :: run_verify`、`tools/agent_r1.py :: run_verify`

---

## `deploy/test_domain.py`

### `stream_chat()`

**调用：** `Request`、`decode`、`dumps`、`encode`、`get`、`loads`、`startswith`、`strip`、`time`、`urlopen`

**被调用：** 无（入口函数或未被引用）

---

## `deploy/test_public.py`

### `stream_chat()`

**调用：** `Request`、`decode`、`dumps`、`encode`、`get`、`loads`、`startswith`、`strip`、`time`、`urlopen`

**被调用：** 无（入口函数或未被引用）

---

## `deploy/upload_7b.py`

### `progress()`

**调用：** `print`

**被调用：** 无（入口函数或未被引用）

---

## `deploy/upload_7b_resume.py`

### `connect()`

**调用：** `AutoAddPolicy`、`SSHClient`、`set_missing_host_key_policy`

**被调用：** 无（入口函数或未被引用）

### `remote_size()`

**调用：** `close`、`open_sftp`、`stat`

**被调用：** 无（入口函数或未被引用）

---

## `deploy/upload_shards.py`

### `connect()`

**调用：** `AutoAddPolicy`、`SSHClient`、`set_missing_host_key_policy`

**被调用：** 无（入口函数或未被引用）

### `rsize()`

**调用：** `close`、`open_sftp`、`stat`

**被调用：** 无（入口函数或未被引用）

---

## `deploy/watch_server.py`

### `connect()`

**调用：** `AutoAddPolicy`、`SSHClient`、`set_missing_host_key_policy`

**被调用：** 无（入口函数或未被引用）

### `run()`

**调用：** `decode`、`exec_command`、`read`、`strip`

**被调用：** `deploy/stage/agent_r1.py :: run_verify`、`tools/agent_r1.py :: run_verify`

---

## `deploy/worker.py`

### `_grams()`

**调用：** `isspace`、`join`、`len`、`range`

**被调用：** `deploy/package/worker.py :: build_index`、`deploy/package/worker.py :: retrieve`、`deploy/stage/serve_r1.py :: build_index`、`deploy/stage/serve_r1.py :: retrieve`、`deploy/stage/worker.py :: build_index`、`deploy/stage/worker.py :: retrieve`、`deploy/worker.py :: build_index`、`deploy/worker.py :: retrieve`、`tools/serve_r1.py :: build_index`、`tools/serve_r1.py :: load_olympiad`、`tools/serve_r1.py :: retrieve`、`tools/serve_r1.py :: retrieve_olympiad`

### `_request()`

**调用：** `HTTPConnection`、`close`、`dumps`、`encode`、`getresponse`、`read`、`request`、`urlparse`

**被调用：** `deploy/worker.py :: poll`、`deploy/worker.py :: post`

### `answer()`

**调用：** `Request`、`decode`、`dumps`、`encode`、`get`、`int`、`join`、`len`、`loads`、`lstrip`、`print`、`retrieve`、`send_chunk`、`send_done`、`split`、`startswith`、`strip`、`time`、`urlopen`

**被调用：** `deploy/package/worker.py :: main`、`deploy/stage/worker.py :: main`、`deploy/worker.py :: main`

### `build_index()`

**调用：** `_grams`、`append`、`exists`、`len`、`max`、`open`、`print`、`range`、`read`、`strip`

**被调用：** `deploy/package/worker.py :: main`、`deploy/stage/serve_r1.py :: main`、`deploy/stage/worker.py :: main`、`deploy/worker.py :: main`、`src/solver.c :: main`、`tools/serve_r1.py :: main`

### `main()`

**调用：** `ArgumentParser`、`add_argument`、`answer`、`build_index`、`get`、`parse_args`、`poll`、`print`、`rstrip`、`send_chunk`、`send_done`、`sleep`

**被调用：** 无（入口函数或未被引用）

### `poll()`

**调用：** `_request`、`loads`、`print`

**被调用：** `deploy/package/worker.py :: main`、`deploy/stage/worker.py :: main`、`deploy/worker.py :: main`

### `post()`

**调用：** `_request`

**被调用：** `deploy/worker.py :: send_chunk`、`deploy/worker.py :: send_done`

### `retrieve()`

**调用：** `_grams`、`append`、`enumerate`、`len`、`sort`

**被调用：** `deploy/package/worker.py :: answer`、`deploy/stage/serve_r1.py :: do_POST`、`deploy/stage/worker.py :: answer`、`deploy/worker.py :: answer`、`tools/serve_r1.py :: do_POST`

### `send_chunk()`

**调用：** `post`、`print`

**被调用：** `deploy/package/worker.py :: answer`、`deploy/package/worker.py :: main`、`deploy/stage/worker.py :: answer`、`deploy/stage/worker.py :: main`、`deploy/worker.py :: answer`、`deploy/worker.py :: main`

### `send_done()`

**调用：** `post`、`print`

**被调用：** `deploy/package/worker.py :: answer`、`deploy/package/worker.py :: main`、`deploy/stage/worker.py :: answer`、`deploy/stage/worker.py :: main`、`deploy/worker.py :: answer`、`deploy/worker.py :: main`

---

## `src/ai.c`

### `adamw_step()`

**调用：** `grad_norm`、`powf`、`sqrtf`

**被调用：** `src/ai.c :: train`、`src/gui.c :: train`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: train`、`src/server.c :: train`、`src/test_answer.c :: train`

### `ai_mode()`

**调用：** `chat_generate`、`chat_reply`、`ctx_append`、`eval_expr`、`fflush`、`fgets`、`free`、`is_arith_s`、`isnan`、`memmove`、`printf`、`snprintf`、`solve_linear`、`strchr`、`strcmp`、`strcspn`、`to_utf8`、`try_rules`

**被调用：** `src/ai.c :: main`

### `alloc_activations()`

**调用：** `calloc`、`falloc`

**被调用：** `src/ai.c :: gradcheck`、`src/ai.c :: main`、`src/gui.c :: gradcheck`、`src/gui.c :: main`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: main`、`src/server.c :: gradcheck`、`src/server.c :: main`、`src/test_answer.c :: gradcheck`、`src/test_answer.c :: main`

### `arith_eval()`

**调用：** `e_expr`、`fclose`、`fgets`、`fopen`、`gen_text`、`printf`、`snprintf`、`sscanf`、`strtol`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`

### `ask_mode()`

**调用：** `chat_generate`、`ctx_append`、`printf`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`

### `backward()`

**调用：** `collapse`、`memcpy`、`memset`、`mm_nt`、`mm_tn`、`rmsnorm_bwd`、`sqrtf`

**被调用：** `src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: gradcheck`、`src/gui.c :: train`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: train`、`src/server.c :: gradcheck`、`src/server.c :: train`、`src/test_answer.c :: gradcheck`、`src/test_answer.c :: train`

### `chat_generate()`

**调用：** `expf`、`fflush`、`forward`、`frand`、`putchar`、`strlen`

**被调用：** `src/ai.c :: ai_mode`、`src/ai.c :: ask_mode`、`src/ai.c :: chat_mode`、`src/gui.c :: ask_mode`、`src/gui.c :: chat_mode`、`src/nanogpt.c :: ask_mode`、`src/nanogpt.c :: chat_mode`、`src/server.c :: ask_mode`、`src/server.c :: chat_mode`、`src/test_answer.c :: ask_mode`、`src/test_answer.c :: chat_mode`

### `chat_mode()`

**调用：** `chat_generate`、`ctx_append`、`fflush`、`fgets`、`memmove`、`printf`、`strcmp`、`strcspn`、`strncpy`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`

### `chat_reply()`

**调用：** `has`、`localtime`、`printf`、`time`

**被调用：** `src/ai.c :: ai_mode`、`src/gui.c :: answer_q`、`src/server.c :: answer_q`、`src/solver.c :: handle`、`src/test_answer.c :: answer_q`、`tools/gui_part.c :: answer_q`、`tools/server_part.c :: answer_q`

### `cn_digit()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: collect_numbers`、`src/ai.c :: parse_cn`、`src/gui.c :: collect_numbers`、`src/gui.c :: parse_cn`、`src/server.c :: collect_numbers`、`src/server.c :: parse_cn`、`src/solver.c :: collect_numbers`、`src/solver.c :: parse_cn`、`src/test_answer.c :: collect_numbers`、`src/test_answer.c :: parse_cn`

### `collect_numbers()`

**调用：** `cn_digit`、`parse_cn`、`strtod`、`u8_next`、`u8_prev`

**被调用：** `src/ai.c :: try_rules`、`src/gui.c :: try_rules`、`src/server.c :: try_rules`、`src/solver.c :: try_rules`、`src/test_answer.c :: try_rules`

### `ctx_append()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: ai_mode`、`src/ai.c :: ask_mode`、`src/ai.c :: chat_mode`、`src/gui.c :: ask_mode`、`src/gui.c :: chat_mode`、`src/nanogpt.c :: ask_mode`、`src/nanogpt.c :: chat_mode`、`src/server.c :: ask_mode`、`src/server.c :: chat_mode`、`src/test_answer.c :: ask_mode`、`src/test_answer.c :: chat_mode`

### `e_expr()`

**调用：** `e_skip`、`e_term`

**被调用：** `src/ai.c :: arith_eval`、`src/ai.c :: e_prim`、`src/ai.c :: eval_expr`、`src/gui.c :: arith_eval`、`src/gui.c :: e_prim`、`src/gui.c :: eval_expr`、`src/nanogpt.c :: arith_eval`、`src/nanogpt.c :: e_prim`、`src/nanogpt.c :: eval_expr`、`src/server.c :: arith_eval`、`src/server.c :: e_prim`、`src/server.c :: eval_expr`

### `e_pow()`

**调用：** `e_prim`、`e_skip`、`pow`

**被调用：** `src/ai.c :: e_term`、`src/gui.c :: e_term`、`src/nanogpt.c :: e_term`、`src/server.c :: e_term`、`src/test_answer.c :: e_term`

### `e_prim()`

**调用：** `e_expr`、`e_skip`、`strtod`

**被调用：** `src/ai.c :: e_pow`、`src/gui.c :: e_pow`、`src/nanogpt.c :: e_pow`、`src/server.c :: e_pow`、`src/test_answer.c :: e_pow`

### `e_skip()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: e_expr`、`src/ai.c :: e_pow`、`src/ai.c :: e_prim`、`src/ai.c :: e_term`、`src/gui.c :: e_expr`、`src/gui.c :: e_pow`、`src/gui.c :: e_prim`、`src/gui.c :: e_term`、`src/nanogpt.c :: e_expr`、`src/nanogpt.c :: e_pow`、`src/nanogpt.c :: e_prim`、`src/nanogpt.c :: e_term`

### `e_term()`

**调用：** `e_pow`、`e_skip`

**被调用：** `src/ai.c :: e_expr`、`src/gui.c :: e_expr`、`src/nanogpt.c :: e_expr`、`src/server.c :: e_expr`、`src/test_answer.c :: e_expr`

### `emit()`

**调用：** `eval_expr`、`isnan`、`printf`

**被调用：** `deploy/stage/agent_r1.py :: do_POST`、`deploy/stage/agent_r1.py :: handle_task`、`deploy/stage/agent_r1.py :: pick_file`、`deploy/stage/serve_r1.py :: do_POST`、`src/ai.c :: try_rules`、`src/gui.c :: try_rules`、`src/server.c :: try_rules`、`src/solver.c :: try_rules`、`src/test_answer.c :: try_rules`、`tools/agent_r1.py :: do_POST`、`tools/agent_r1.py :: handle_task`、`tools/agent_r1.py :: pick_file`

### `eval_expr()`

**调用：** `e_expr`

**被调用：** `src/ai.c :: ai_mode`、`src/ai.c :: emit`、`src/ai.c :: verify_chain`、`src/gui.c :: answer_q`、`src/gui.c :: emit`、`src/gui.c :: verify_chain`、`src/nanogpt.c :: verify_chain`、`src/server.c :: answer_q`、`src/server.c :: emit`、`src/server.c :: verify_chain`、`src/test_answer.c :: answer_q`、`src/test_answer.c :: emit`

### `eval_loss()`

**调用：** `forward`、`loss_and_grad`、`sample_batch`

**被调用：** `src/ai.c :: train`、`src/gui.c :: train`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: train`、`src/server.c :: train`、`src/test_answer.c :: train`

### `first_any()`

**调用：** 无（叶子函数）

**被调用：** 无（入口函数或未被引用）

### `first_of()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: try_rules`、`src/gui.c :: try_rules`、`src/server.c :: try_rules`、`src/solver.c :: try_rules`、`src/test_answer.c :: try_rules`

### `forward()`

**调用：** `collapse`、`expf`、`memset`、`mm_nn`、`rmsnorm_fwd`、`sqrtf`

**被调用：** `src/ai.c :: chat_generate`、`src/ai.c :: eval_loss`、`src/ai.c :: gen_text`、`src/ai.c :: generate`、`src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: chat_generate`、`src/gui.c :: eval_loss`、`src/gui.c :: gen_text`、`src/gui.c :: generate`、`src/gui.c :: gradcheck`、`src/gui.c :: train`

### `frand()`

**调用：** `xrand`

**被调用：** `src/ai.c :: chat_generate`、`src/ai.c :: gen_text`、`src/ai.c :: generate`、`src/ai.c :: gradcheck`、`src/ai.c :: nrand`、`src/gui.c :: chat_generate`、`src/gui.c :: gen_text`、`src/gui.c :: generate`、`src/gui.c :: gradcheck`、`src/gui.c :: nrand`、`src/nanogpt.c :: chat_generate`、`src/nanogpt.c :: gen_text`

### `gen_text()`

**调用：** `expf`、`forward`、`frand`

**被调用：** `src/ai.c :: arith_eval`、`src/ai.c :: looks_utf8`、`src/ai.c :: think_mode`、`src/gui.c :: arith_eval`、`src/gui.c :: looks_utf8`、`src/gui.c :: think_mode`、`src/nanogpt.c :: arith_eval`、`src/nanogpt.c :: looks_utf8`、`src/nanogpt.c :: think_mode`、`src/server.c :: arith_eval`、`src/server.c :: looks_utf8`、`src/server.c :: think_mode`

### `generate()`

**调用：** `expf`、`fflush`、`forward`、`frand`、`printf`、`putchar`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`

### `grad_norm()`

**调用：** `sqrt`

**被调用：** `src/ai.c :: adamw_step`、`src/gui.c :: adamw_step`、`src/nanogpt.c :: adamw_step`、`src/nanogpt_dbl.c :: adamw_step`、`src/server.c :: adamw_step`、`src/test_answer.c :: adamw_step`

### `gradcheck()`

**调用：** `alloc_activations`、`backward`、`fabs`、`fabsf`、`forward`、`frand`、`free`、`loss_and_grad`、`malloc`、`printf`、`sample_batch`、`sqrt`、`xrand`、`zero_grads`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`

### `has()`

**调用：** `strstr`

**被调用：** `src/ai.c :: chat_reply`、`src/ai.c :: try_rules`、`src/gui.c :: chat_reply`、`src/gui.c :: try_rules`、`src/server.c :: chat_reply`、`src/server.c :: try_rules`、`src/solver.c :: chat_reply`、`src/solver.c :: try_rules`、`src/test_answer.c :: chat_reply`、`src/test_answer.c :: try_rules`

### `init_params()`

**调用：** `add_param`、`is_bias`、`memset`、`nrand`、`printf`、`snprintf`、`strcmp`

**被调用：** `src/ai.c :: main`、`src/gui.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`、`src/server.c :: main`、`src/test_answer.c :: main`、`tools/gui_part.c :: main`、`tools/server_part.c :: main`、`tools/test_main.c :: main`

### `is_arith_s()`

**调用：** `isdigit`、`strchr`

**被调用：** `src/ai.c :: ai_mode`、`src/gui.c :: answer_q`、`src/server.c :: answer_q`、`src/test_answer.c :: answer_q`、`tools/gui_part.c :: answer_q`、`tools/server_part.c :: answer_q`

### `is_bias()`

**调用：** `strstr`

**被调用：** `src/ai.c :: init_params`、`src/gui.c :: init_params`、`src/nanogpt.c :: init_params`、`src/nanogpt_dbl.c :: init_params`、`src/server.c :: init_params`、`src/test_answer.c :: init_params`

### `load_corpus()`

**调用：** `fclose`、`fopen`、`fprintf`、`fread`、`fseek`、`ftell`、`malloc`、`memset`、`printf`

**被调用：** `src/ai.c :: main`、`src/gui.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`、`src/server.c :: main`、`src/test_answer.c :: main`、`tools/gui_part.c :: main`、`tools/server_part.c :: main`、`tools/test_main.c :: main`

### `load_weights()`

**调用：** `fclose`、`fopen`、`fprintf`、`fread`、`memcmp`、`printf`、`strncmp`

**被调用：** `src/ai.c :: main`、`src/gui.c :: main`、`src/nanogpt.c :: main`、`src/server.c :: main`、`src/test_answer.c :: main`、`tools/gui_part.c :: main`、`tools/server_part.c :: main`、`tools/test_main.c :: main`

### `looks_utf8()`

**调用：** `MultiByteToWideChar`、`WideCharToMultiByte`、`free`、`gen_text`、`malloc`、`strcpy`、`strlen`、`to_utf8`

**被调用：** `src/test_answer.c :: answer_q`

### `loss_and_grad()`

**调用：** `expf`、`logf`

**被调用：** `src/ai.c :: eval_loss`、`src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: eval_loss`、`src/gui.c :: gradcheck`、`src/gui.c :: train`、`src/nanogpt.c :: eval_loss`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: eval_loss`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: train`

### `main()`

**调用：** `SetConsoleOutputCP`、`ai_mode`、`alloc_activations`、`arith_eval`、`ask_mode`、`atoi`、`chat_mode`、`fprintf`、`free`、`generate`、`gradcheck`、`init_params`、`load_corpus`、`load_weights`、`printf`、`save_weights`、`strcmp`、`strstr`、`think_mode`、`to_utf8`、`train`

**被调用：** 无（入口函数或未被引用）

### `max_num()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: try_rules`、`src/gui.c :: try_rules`、`src/server.c :: try_rules`、`src/solver.c :: try_rules`、`src/test_answer.c :: try_rules`

### `mm_nn()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: forward`、`src/gui.c :: forward`、`src/nanogpt.c :: forward`、`src/nanogpt_dbl.c :: forward`、`src/server.c :: forward`、`src/test_answer.c :: forward`

### `mm_nt()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: backward`、`src/gui.c :: backward`、`src/nanogpt.c :: backward`、`src/nanogpt_dbl.c :: backward`、`src/server.c :: backward`、`src/test_answer.c :: backward`

### `mm_tn()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: backward`、`src/gui.c :: backward`、`src/nanogpt.c :: backward`、`src/nanogpt_dbl.c :: backward`、`src/server.c :: backward`、`src/test_answer.c :: backward`

### `nrand()`

**调用：** `_Pragma`、`cosf`、`frand`、`logf`、`sqrtf`

**被调用：** `src/ai.c :: init_params`、`src/gui.c :: init_params`、`src/nanogpt.c :: init_params`、`src/nanogpt_dbl.c :: init_params`、`src/server.c :: init_params`、`src/test_answer.c :: init_params`

### `parse_cn()`

**调用：** `cn_digit`、`u8_next`

**被调用：** `src/ai.c :: collect_numbers`、`src/gui.c :: collect_numbers`、`src/server.c :: collect_numbers`、`src/solver.c :: collect_numbers`、`src/test_answer.c :: collect_numbers`

### `rmsnorm_bwd()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: backward`、`src/gui.c :: backward`、`src/nanogpt.c :: backward`、`src/nanogpt_dbl.c :: backward`、`src/server.c :: backward`、`src/test_answer.c :: backward`

### `rmsnorm_fwd()`

**调用：** `sqrtf`

**被调用：** `src/ai.c :: forward`、`src/gui.c :: forward`、`src/nanogpt.c :: forward`、`src/nanogpt_dbl.c :: forward`、`src/server.c :: forward`、`src/test_answer.c :: forward`

### `sample_batch()`

**调用：** `xrand`

**被调用：** `src/ai.c :: eval_loss`、`src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: eval_loss`、`src/gui.c :: gradcheck`、`src/gui.c :: train`、`src/nanogpt.c :: eval_loss`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: eval_loss`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: train`

### `save_weights()`

**调用：** `fclose`、`fopen`、`fprintf`、`fwrite`、`memset`、`printf`、`strncpy`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`

### `solve_linear()`

**调用：** `fabs`、`lin_term`、`snprintf`、`strchr`

**被调用：** `src/ai.c :: ai_mode`、`src/gui.c :: answer_q`、`src/server.c :: answer_q`、`src/solver.c :: handle`、`src/solver.c :: main`、`src/test_answer.c :: answer_q`、`tools/gui_part.c :: answer_q`、`tools/server_part.c :: answer_q`

### `think_mode()`

**调用：** `gen_text`、`lin_term`、`memset`、`printf`、`snprintf`、`strcspn`、`verify_chain`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`

### `train()`

**调用：** `adamw_step`、`backward`、`clock`、`cosf`、`eval_loss`、`fflush`、`forward`、`loss_and_grad`、`printf`、`sample_batch`、`zero_grads`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`、`tools/train_lora.py :: main`

### `try_rules()`

**调用：** `collect_numbers`、`emit`、`first_of`、`has`、`max_num`、`snprintf`、`strlen`、`strncat`

**被调用：** `src/ai.c :: ai_mode`、`src/gui.c :: answer_q`、`src/server.c :: answer_q`、`src/solver.c :: handle`、`src/test_answer.c :: answer_q`、`tools/gui_part.c :: answer_q`、`tools/server_part.c :: answer_q`

### `u8_next()`

**调用：** `u8_prev`

**被调用：** `src/ai.c :: collect_numbers`、`src/ai.c :: parse_cn`、`src/gui.c :: collect_numbers`、`src/gui.c :: parse_cn`、`src/server.c :: collect_numbers`、`src/server.c :: parse_cn`、`src/solver.c :: collect_numbers`、`src/solver.c :: parse_cn`、`src/test_answer.c :: collect_numbers`、`src/test_answer.c :: parse_cn`

### `verify_chain()`

**调用：** `atof`、`eval_expr`、`fabs`、`fmax`、`isnan`、`memcpy`、`memset`、`strchr`、`strlen`、`strrchr`、`strstr`

**被调用：** `src/ai.c :: think_mode`、`src/gui.c :: think_mode`、`src/nanogpt.c :: think_mode`、`src/server.c :: think_mode`、`src/test_answer.c :: think_mode`

### `xrand()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: frand`、`src/ai.c :: gradcheck`、`src/ai.c :: sample_batch`、`src/gui.c :: frand`、`src/gui.c :: gradcheck`、`src/gui.c :: sample_batch`、`src/nanogpt.c :: frand`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: sample_batch`、`src/nanogpt_dbl.c :: frand`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: sample_batch`

### `zero_grads()`

**调用：** `memset`

**被调用：** `src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: gradcheck`、`src/gui.c :: train`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: train`、`src/server.c :: gradcheck`、`src/server.c :: train`、`src/test_answer.c :: gradcheck`、`src/test_answer.c :: train`

---

## `src/gui.c`

### `abs_path()`

**调用：** `_getcwd`、`snprintf`

**被调用：** `src/gui.c :: answer_q`、`src/server.c :: load_sessions`

### `adamw_step()`

**调用：** `grad_norm`、`powf`、`sqrtf`

**被调用：** `src/ai.c :: train`、`src/gui.c :: train`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: train`、`src/server.c :: train`、`src/test_answer.c :: train`

### `alloc_activations()`

**调用：** `calloc`、`falloc`

**被调用：** `src/ai.c :: gradcheck`、`src/ai.c :: main`、`src/gui.c :: gradcheck`、`src/gui.c :: main`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: main`、`src/server.c :: gradcheck`、`src/server.c :: main`、`src/test_answer.c :: gradcheck`、`src/test_answer.c :: main`

### `answer_q()`

**调用：** `MessageBoxW`、`MultiByteToWideChar`、`WideCharToMultiByte`、`abs_path`、`chat_reply`、`eval_expr`、`fclose`、`fopen`、`fread`、`fs_exec`、`is_arith_s`、`isnan`、`malloc`、`parse_fs_intent`、`snprintf`、`solve_linear`、`strchr`、`strcmp`、`strlen`、`strncat`、`try_rules`、`utf8_to_w`、`w_to_utf8`

**被调用：** `src/gui.c :: do_send`、`src/server.c :: load_sessions`、`src/test_answer.c :: main`、`tools/gui_part.c :: do_send`、`tools/server_part.c :: load_sessions`、`tools/test_main.c :: main`

### `append_history()`

**调用：** `GetWindowTextLengthW`、`SendMessageW`、`wcscat`

**被调用：** `src/gui.c :: do_send`、`src/gui.c :: wndproc`、`tools/gui_part.c :: do_send`、`tools/gui_part.c :: wndproc`

### `arith_eval()`

**调用：** `e_expr`、`fclose`、`fgets`、`fopen`、`gen_text`、`printf`、`snprintf`、`sscanf`、`strtol`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`

### `ask_mode()`

**调用：** `chat_generate`、`ctx_append`、`printf`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`

### `backward()`

**调用：** `collapse`、`memcpy`、`memset`、`mm_nt`、`mm_tn`、`rmsnorm_bwd`、`sqrtf`

**被调用：** `src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: gradcheck`、`src/gui.c :: train`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: train`、`src/server.c :: gradcheck`、`src/server.c :: train`、`src/test_answer.c :: gradcheck`、`src/test_answer.c :: train`

### `char_id()`

**调用：** 无（叶子函数）

**被调用：** `src/gui.c :: load_corpus`、`src/gui.c :: str_to_ids`、`src/nanogpt.c :: load_corpus`、`src/nanogpt.c :: str_to_ids`、`src/server.c :: load_corpus`、`src/server.c :: str_to_ids`

### `chat_generate()`

**调用：** `expf`、`fflush`、`forward`、`frand`、`fwrite`、`id_to_out`、`str_to_ids`

**被调用：** `src/ai.c :: ai_mode`、`src/ai.c :: ask_mode`、`src/ai.c :: chat_mode`、`src/gui.c :: ask_mode`、`src/gui.c :: chat_mode`、`src/nanogpt.c :: ask_mode`、`src/nanogpt.c :: chat_mode`、`src/server.c :: ask_mode`、`src/server.c :: chat_mode`、`src/test_answer.c :: ask_mode`、`src/test_answer.c :: chat_mode`

### `chat_mode()`

**调用：** `chat_generate`、`ctx_append`、`fflush`、`fgets`、`memmove`、`printf`、`strcmp`、`strcspn`、`strncpy`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`

### `chat_reply()`

**调用：** `has`、`localtime`、`pick_reply`、`repf`、`strlen`、`time`

**被调用：** `src/ai.c :: ai_mode`、`src/gui.c :: answer_q`、`src/server.c :: answer_q`、`src/solver.c :: handle`、`src/test_answer.c :: answer_q`、`tools/gui_part.c :: answer_q`、`tools/server_part.c :: answer_q`

### `cmap_init()`

**调用：** 无（叶子函数）

**被调用：** `src/gui.c :: load_corpus`、`src/gui.c :: load_weights`、`src/nanogpt.c :: load_corpus`、`src/nanogpt.c :: load_weights`、`src/server.c :: load_corpus`、`src/server.c :: load_weights`

### `cmap_put()`

**调用：** 无（叶子函数）

**被调用：** `src/gui.c :: load_corpus`、`src/gui.c :: load_weights`、`src/nanogpt.c :: load_corpus`、`src/nanogpt.c :: load_weights`、`src/server.c :: load_corpus`、`src/server.c :: load_weights`

### `cn_digit()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: collect_numbers`、`src/ai.c :: parse_cn`、`src/gui.c :: collect_numbers`、`src/gui.c :: parse_cn`、`src/server.c :: collect_numbers`、`src/server.c :: parse_cn`、`src/solver.c :: collect_numbers`、`src/solver.c :: parse_cn`、`src/test_answer.c :: collect_numbers`、`src/test_answer.c :: parse_cn`

### `collect_numbers()`

**调用：** `cn_digit`、`parse_cn`、`strtod`、`u8_next`、`u8_prev`

**被调用：** `src/ai.c :: try_rules`、`src/gui.c :: try_rules`、`src/server.c :: try_rules`、`src/solver.c :: try_rules`、`src/test_answer.c :: try_rules`

### `ctx_append()`

**调用：** `str_to_ids`

**被调用：** `src/ai.c :: ai_mode`、`src/ai.c :: ask_mode`、`src/ai.c :: chat_mode`、`src/gui.c :: ask_mode`、`src/gui.c :: chat_mode`、`src/nanogpt.c :: ask_mode`、`src/nanogpt.c :: chat_mode`、`src/server.c :: ask_mode`、`src/server.c :: chat_mode`、`src/test_answer.c :: ask_mode`、`src/test_answer.c :: chat_mode`

### `do_send()`

**调用：** `GetWindowTextW`、`SetWindowTextW`、`answer_q`、`append_history`、`fclose`、`fopen`、`fprintf`、`free`、`snprintf`、`u8_count`、`utf8_to_w`、`w_to_utf8`

**被调用：** `src/gui.c :: wndproc`、`tools/gui_part.c :: wndproc`

### `e_expr()`

**调用：** `e_skip`、`e_term`

**被调用：** `src/ai.c :: arith_eval`、`src/ai.c :: e_prim`、`src/ai.c :: eval_expr`、`src/gui.c :: arith_eval`、`src/gui.c :: e_prim`、`src/gui.c :: eval_expr`、`src/nanogpt.c :: arith_eval`、`src/nanogpt.c :: e_prim`、`src/nanogpt.c :: eval_expr`、`src/server.c :: arith_eval`、`src/server.c :: e_prim`、`src/server.c :: eval_expr`

### `e_pow()`

**调用：** `e_prim`、`e_skip`、`pow`

**被调用：** `src/ai.c :: e_term`、`src/gui.c :: e_term`、`src/nanogpt.c :: e_term`、`src/server.c :: e_term`、`src/test_answer.c :: e_term`

### `e_prim()`

**调用：** `e_expr`、`e_skip`、`strtod`

**被调用：** `src/ai.c :: e_pow`、`src/gui.c :: e_pow`、`src/nanogpt.c :: e_pow`、`src/server.c :: e_pow`、`src/test_answer.c :: e_pow`

### `e_skip()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: e_expr`、`src/ai.c :: e_pow`、`src/ai.c :: e_prim`、`src/ai.c :: e_term`、`src/gui.c :: e_expr`、`src/gui.c :: e_pow`、`src/gui.c :: e_prim`、`src/gui.c :: e_term`、`src/nanogpt.c :: e_expr`、`src/nanogpt.c :: e_pow`、`src/nanogpt.c :: e_prim`、`src/nanogpt.c :: e_term`

### `e_term()`

**调用：** `e_pow`、`e_skip`

**被调用：** `src/ai.c :: e_expr`、`src/gui.c :: e_expr`、`src/nanogpt.c :: e_expr`、`src/server.c :: e_expr`、`src/test_answer.c :: e_expr`

### `emit()`

**调用：** `eval_expr`、`isnan`、`repf`

**被调用：** `deploy/stage/agent_r1.py :: do_POST`、`deploy/stage/agent_r1.py :: handle_task`、`deploy/stage/agent_r1.py :: pick_file`、`deploy/stage/serve_r1.py :: do_POST`、`src/ai.c :: try_rules`、`src/gui.c :: try_rules`、`src/server.c :: try_rules`、`src/solver.c :: try_rules`、`src/test_answer.c :: try_rules`、`tools/agent_r1.py :: do_POST`、`tools/agent_r1.py :: handle_task`、`tools/agent_r1.py :: pick_file`

### `eval_expr()`

**调用：** `e_expr`

**被调用：** `src/ai.c :: ai_mode`、`src/ai.c :: emit`、`src/ai.c :: verify_chain`、`src/gui.c :: answer_q`、`src/gui.c :: emit`、`src/gui.c :: verify_chain`、`src/nanogpt.c :: verify_chain`、`src/server.c :: answer_q`、`src/server.c :: emit`、`src/server.c :: verify_chain`、`src/test_answer.c :: answer_q`、`src/test_answer.c :: emit`

### `eval_loss()`

**调用：** `forward`、`loss_and_grad`、`sample_batch`

**被调用：** `src/ai.c :: train`、`src/gui.c :: train`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: train`、`src/server.c :: train`、`src/test_answer.c :: train`

### `first_any()`

**调用：** 无（叶子函数）

**被调用：** 无（入口函数或未被引用）

### `first_of()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: try_rules`、`src/gui.c :: try_rules`、`src/server.c :: try_rules`、`src/solver.c :: try_rules`、`src/test_answer.c :: try_rules`

### `forward()`

**调用：** `collapse`、`expf`、`memset`、`mm_nn`、`rmsnorm_fwd`、`sqrtf`

**被调用：** `src/ai.c :: chat_generate`、`src/ai.c :: eval_loss`、`src/ai.c :: gen_text`、`src/ai.c :: generate`、`src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: chat_generate`、`src/gui.c :: eval_loss`、`src/gui.c :: gen_text`、`src/gui.c :: generate`、`src/gui.c :: gradcheck`、`src/gui.c :: train`

### `frand()`

**调用：** `xrand`

**被调用：** `src/ai.c :: chat_generate`、`src/ai.c :: gen_text`、`src/ai.c :: generate`、`src/ai.c :: gradcheck`、`src/ai.c :: nrand`、`src/gui.c :: chat_generate`、`src/gui.c :: gen_text`、`src/gui.c :: generate`、`src/gui.c :: gradcheck`、`src/gui.c :: nrand`、`src/nanogpt.c :: chat_generate`、`src/nanogpt.c :: gen_text`

### `fs_exec()`

**调用：** `_mkdir`、`fclose`、`fopen`、`fwrite`、`remove`、`snprintf`、`strcmp`

**被调用：** `src/gui.c :: answer_q`

### `gen_text()`

**调用：** `expf`、`forward`、`frand`、`id_to_out`、`str_to_ids`

**被调用：** `src/ai.c :: arith_eval`、`src/ai.c :: looks_utf8`、`src/ai.c :: think_mode`、`src/gui.c :: arith_eval`、`src/gui.c :: looks_utf8`、`src/gui.c :: think_mode`、`src/nanogpt.c :: arith_eval`、`src/nanogpt.c :: looks_utf8`、`src/nanogpt.c :: think_mode`、`src/server.c :: arith_eval`、`src/server.c :: looks_utf8`、`src/server.c :: think_mode`

### `generate()`

**调用：** `expf`、`fflush`、`forward`、`frand`、`fwrite`、`id_to_out`、`printf`、`str_to_ids`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`

### `grad_norm()`

**调用：** `sqrt`

**被调用：** `src/ai.c :: adamw_step`、`src/gui.c :: adamw_step`、`src/nanogpt.c :: adamw_step`、`src/nanogpt_dbl.c :: adamw_step`、`src/server.c :: adamw_step`、`src/test_answer.c :: adamw_step`

### `gradcheck()`

**调用：** `alloc_activations`、`backward`、`fabs`、`fabsf`、`forward`、`frand`、`free`、`loss_and_grad`、`malloc`、`printf`、`sample_batch`、`sqrt`、`xrand`、`zero_grads`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`

### `has()`

**调用：** `strstr`

**被调用：** `src/ai.c :: chat_reply`、`src/ai.c :: try_rules`、`src/gui.c :: chat_reply`、`src/gui.c :: try_rules`、`src/server.c :: chat_reply`、`src/server.c :: try_rules`、`src/solver.c :: chat_reply`、`src/solver.c :: try_rules`、`src/test_answer.c :: chat_reply`、`src/test_answer.c :: try_rules`

### `id_to_out()`

**调用：** `u8_put`

**被调用：** `src/gui.c :: chat_generate`、`src/gui.c :: gen_text`、`src/gui.c :: generate`、`src/nanogpt.c :: chat_generate`、`src/nanogpt.c :: gen_text`、`src/nanogpt.c :: generate`、`src/server.c :: chat_generate`、`src/server.c :: gen_text`、`src/server.c :: generate`

### `init_params()`

**调用：** `add_param`、`is_bias`、`memset`、`nrand`、`printf`、`snprintf`、`strcmp`

**被调用：** `src/ai.c :: main`、`src/gui.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`、`src/server.c :: main`、`src/test_answer.c :: main`、`tools/gui_part.c :: main`、`tools/server_part.c :: main`、`tools/test_main.c :: main`

### `inp_proc()`

**调用：** `CallWindowProc`、`GetParent`、`SendMessage`

**被调用：** 无（入口函数或未被引用）

### `is_arith_s()`

**调用：** `isdigit`、`strchr`

**被调用：** `src/ai.c :: ai_mode`、`src/gui.c :: answer_q`、`src/server.c :: answer_q`、`src/test_answer.c :: answer_q`、`tools/gui_part.c :: answer_q`、`tools/server_part.c :: answer_q`

### `is_bias()`

**调用：** `strstr`

**被调用：** `src/ai.c :: init_params`、`src/gui.c :: init_params`、`src/nanogpt.c :: init_params`、`src/nanogpt_dbl.c :: init_params`、`src/server.c :: init_params`、`src/test_answer.c :: init_params`

### `load_corpus()`

**调用：** `char_id`、`cmap_init`、`cmap_put`、`fclose`、`fopen`、`fprintf`、`fread`、`fseek`、`ftell`、`malloc`、`memset`、`printf`、`u8_get`

**被调用：** `src/ai.c :: main`、`src/gui.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`、`src/server.c :: main`、`src/test_answer.c :: main`、`tools/gui_part.c :: main`、`tools/server_part.c :: main`、`tools/test_main.c :: main`

### `load_weights()`

**调用：** `cmap_init`、`cmap_put`、`fclose`、`fopen`、`fprintf`、`fread`、`memcmp`、`printf`、`strncmp`

**被调用：** `src/ai.c :: main`、`src/gui.c :: main`、`src/nanogpt.c :: main`、`src/server.c :: main`、`src/test_answer.c :: main`、`tools/gui_part.c :: main`、`tools/server_part.c :: main`、`tools/test_main.c :: main`

### `looks_utf8()`

**调用：** `MultiByteToWideChar`、`WideCharToMultiByte`、`free`、`gen_text`、`malloc`、`strcpy`、`strlen`、`to_utf8`

**被调用：** `src/test_answer.c :: answer_q`

### `loss_and_grad()`

**调用：** `expf`、`logf`

**被调用：** `src/ai.c :: eval_loss`、`src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: eval_loss`、`src/gui.c :: gradcheck`、`src/gui.c :: train`、`src/nanogpt.c :: eval_loss`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: eval_loss`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: train`

### `main()`

**调用：** `CreateWindowW`、`DispatchMessageW`、`GetMessageW`、`GetModuleHandleW`、`LoadCursor`、`MessageBoxA`、`RegisterClassW`、`ShowWindow`、`TranslateMessage`、`alloc_activations`、`init_params`、`load_corpus`、`load_weights`、`memset`

**被调用：** 无（入口函数或未被引用）

### `max_num()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: try_rules`、`src/gui.c :: try_rules`、`src/server.c :: try_rules`、`src/solver.c :: try_rules`、`src/test_answer.c :: try_rules`

### `mm_nn()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: forward`、`src/gui.c :: forward`、`src/nanogpt.c :: forward`、`src/nanogpt_dbl.c :: forward`、`src/server.c :: forward`、`src/test_answer.c :: forward`

### `mm_nt()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: backward`、`src/gui.c :: backward`、`src/nanogpt.c :: backward`、`src/nanogpt_dbl.c :: backward`、`src/server.c :: backward`、`src/test_answer.c :: backward`

### `mm_tn()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: backward`、`src/gui.c :: backward`、`src/nanogpt.c :: backward`、`src/nanogpt_dbl.c :: backward`、`src/server.c :: backward`、`src/test_answer.c :: backward`

### `nrand()`

**调用：** `_Pragma`、`cosf`、`frand`、`logf`、`sqrtf`

**被调用：** `src/ai.c :: init_params`、`src/gui.c :: init_params`、`src/nanogpt.c :: init_params`、`src/nanogpt_dbl.c :: init_params`、`src/server.c :: init_params`、`src/test_answer.c :: init_params`

### `parse_cn()`

**调用：** `cn_digit`、`u8_next`

**被调用：** `src/ai.c :: collect_numbers`、`src/gui.c :: collect_numbers`、`src/server.c :: collect_numbers`、`src/solver.c :: collect_numbers`、`src/test_answer.c :: collect_numbers`

### `parse_fs_intent()`

**调用：** `snprintf`、`strlen`、`strstr`

**被调用：** `src/gui.c :: answer_q`、`src/server.c :: load_sessions`

### `rep()`

**调用：** `memcpy`、`strlen`

**被调用：** `src/gui.c :: repf`、`src/server.c :: repf`、`src/test_answer.c :: repf`、`tools/gui_part.c :: repf`、`tools/server_part.c :: repf`

### `repf()`

**调用：** `rep`、`va_end`、`va_start`、`vsnprintf`

**被调用：** `src/gui.c :: chat_reply`、`src/gui.c :: emit`、`src/server.c :: chat_reply`、`src/server.c :: emit`、`src/test_answer.c :: chat_reply`、`src/test_answer.c :: emit`

### `rmsnorm_bwd()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: backward`、`src/gui.c :: backward`、`src/nanogpt.c :: backward`、`src/nanogpt_dbl.c :: backward`、`src/server.c :: backward`、`src/test_answer.c :: backward`

### `rmsnorm_fwd()`

**调用：** `sqrtf`

**被调用：** `src/ai.c :: forward`、`src/gui.c :: forward`、`src/nanogpt.c :: forward`、`src/nanogpt_dbl.c :: forward`、`src/server.c :: forward`、`src/test_answer.c :: forward`

### `sample_batch()`

**调用：** `xrand`

**被调用：** `src/ai.c :: eval_loss`、`src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: eval_loss`、`src/gui.c :: gradcheck`、`src/gui.c :: train`、`src/nanogpt.c :: eval_loss`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: eval_loss`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: train`

### `save_weights()`

**调用：** `fclose`、`fopen`、`fprintf`、`fwrite`、`memset`、`printf`、`strncpy`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`

### `sess_append()`

**调用：** `memcpy`、`strlen`

**被调用：** `src/test_answer.c :: answer_q`

### `solve_linear()`

**调用：** `fabs`、`lin_term`、`snprintf`、`strchr`

**被调用：** `src/ai.c :: ai_mode`、`src/gui.c :: answer_q`、`src/server.c :: answer_q`、`src/solver.c :: handle`、`src/solver.c :: main`、`src/test_answer.c :: answer_q`、`tools/gui_part.c :: answer_q`、`tools/server_part.c :: answer_q`

### `str_to_ids()`

**调用：** `char_id`、`u8_get`

**被调用：** `src/gui.c :: chat_generate`、`src/gui.c :: ctx_append`、`src/gui.c :: gen_text`、`src/gui.c :: generate`、`src/nanogpt.c :: chat_generate`、`src/nanogpt.c :: ctx_append`、`src/nanogpt.c :: gen_text`、`src/nanogpt.c :: generate`、`src/server.c :: chat_generate`、`src/server.c :: ctx_append`、`src/server.c :: gen_text`、`src/server.c :: generate`

### `think_mode()`

**调用：** `gen_text`、`lin_term`、`memset`、`printf`、`snprintf`、`strcspn`、`verify_chain`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`

### `train()`

**调用：** `adamw_step`、`backward`、`clock`、`cosf`、`eval_loss`、`fflush`、`forward`、`loss_and_grad`、`printf`、`sample_batch`、`zero_grads`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`、`tools/train_lora.py :: main`

### `try_rules()`

**调用：** `collect_numbers`、`emit`、`first_of`、`has`、`max_num`、`pick_reply`、`snprintf`、`strlen`、`strncat`

**被调用：** `src/ai.c :: ai_mode`、`src/gui.c :: answer_q`、`src/server.c :: answer_q`、`src/solver.c :: handle`、`src/test_answer.c :: answer_q`、`tools/gui_part.c :: answer_q`、`tools/server_part.c :: answer_q`

### `u8_count()`

**调用：** 无（叶子函数）

**被调用：** `src/gui.c :: do_send`、`src/server.c :: load_sessions`

### `u8_get()`

**调用：** 无（叶子函数）

**被调用：** `src/gui.c :: load_corpus`、`src/gui.c :: str_to_ids`、`src/nanogpt.c :: load_corpus`、`src/nanogpt.c :: str_to_ids`、`src/server.c :: load_corpus`、`src/server.c :: str_to_ids`

### `u8_next()`

**调用：** `u8_prev`

**被调用：** `src/ai.c :: collect_numbers`、`src/ai.c :: parse_cn`、`src/gui.c :: collect_numbers`、`src/gui.c :: parse_cn`、`src/server.c :: collect_numbers`、`src/server.c :: parse_cn`、`src/solver.c :: collect_numbers`、`src/solver.c :: parse_cn`、`src/test_answer.c :: collect_numbers`、`src/test_answer.c :: parse_cn`

### `u8_put()`

**调用：** 无（叶子函数）

**被调用：** `src/gui.c :: id_to_out`、`src/nanogpt.c :: id_to_out`、`src/server.c :: id_to_out`

### `verify_chain()`

**调用：** `atof`、`eval_expr`、`fabs`、`fmax`、`isnan`、`memcpy`、`memset`、`strchr`、`strlen`、`strrchr`、`strstr`

**被调用：** `src/ai.c :: think_mode`、`src/gui.c :: think_mode`、`src/nanogpt.c :: think_mode`、`src/server.c :: think_mode`、`src/test_answer.c :: think_mode`

### `wndproc()`

**调用：** `CreateFontW`、`CreateWindowW`、`DefWindowProcW`、`LOWORD`、`PostQuitMessage`、`SendMessageW`、`SetFocus`、`SetWindowLongPtrW`、`append_history`、`do_send`

**被调用：** 无（入口函数或未被引用）

### `xrand()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: frand`、`src/ai.c :: gradcheck`、`src/ai.c :: sample_batch`、`src/gui.c :: frand`、`src/gui.c :: gradcheck`、`src/gui.c :: sample_batch`、`src/nanogpt.c :: frand`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: sample_batch`、`src/nanogpt_dbl.c :: frand`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: sample_batch`

### `zero_grads()`

**调用：** `memset`

**被调用：** `src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: gradcheck`、`src/gui.c :: train`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: train`、`src/server.c :: gradcheck`、`src/server.c :: train`、`src/test_answer.c :: gradcheck`、`src/test_answer.c :: train`

---

## `src/nanogpt.c`

### `adamw_step()`

**调用：** `grad_norm`、`powf`、`sqrtf`

**被调用：** `src/ai.c :: train`、`src/gui.c :: train`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: train`、`src/server.c :: train`、`src/test_answer.c :: train`

### `alloc_activations()`

**调用：** `calloc`、`falloc`

**被调用：** `src/ai.c :: gradcheck`、`src/ai.c :: main`、`src/gui.c :: gradcheck`、`src/gui.c :: main`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: main`、`src/server.c :: gradcheck`、`src/server.c :: main`、`src/test_answer.c :: gradcheck`、`src/test_answer.c :: main`

### `arith_eval()`

**调用：** `e_expr`、`fclose`、`fgets`、`fopen`、`gen_text`、`printf`、`snprintf`、`sscanf`、`strtol`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`

### `ask_mode()`

**调用：** `chat_generate`、`ctx_append`、`printf`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`

### `backward()`

**调用：** `collapse`、`memcpy`、`memset`、`mm_nt`、`mm_tn`、`rmsnorm_bwd`、`sqrtf`

**被调用：** `src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: gradcheck`、`src/gui.c :: train`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: train`、`src/server.c :: gradcheck`、`src/server.c :: train`、`src/test_answer.c :: gradcheck`、`src/test_answer.c :: train`

### `char_id()`

**调用：** 无（叶子函数）

**被调用：** `src/gui.c :: load_corpus`、`src/gui.c :: str_to_ids`、`src/nanogpt.c :: load_corpus`、`src/nanogpt.c :: str_to_ids`、`src/server.c :: load_corpus`、`src/server.c :: str_to_ids`

### `chat_generate()`

**调用：** `expf`、`fflush`、`forward`、`frand`、`fwrite`、`id_to_out`、`str_to_ids`

**被调用：** `src/ai.c :: ai_mode`、`src/ai.c :: ask_mode`、`src/ai.c :: chat_mode`、`src/gui.c :: ask_mode`、`src/gui.c :: chat_mode`、`src/nanogpt.c :: ask_mode`、`src/nanogpt.c :: chat_mode`、`src/server.c :: ask_mode`、`src/server.c :: chat_mode`、`src/test_answer.c :: ask_mode`、`src/test_answer.c :: chat_mode`

### `chat_mode()`

**调用：** `chat_generate`、`ctx_append`、`fflush`、`fgets`、`memmove`、`printf`、`strcmp`、`strcspn`、`strncpy`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`

### `cmap_init()`

**调用：** 无（叶子函数）

**被调用：** `src/gui.c :: load_corpus`、`src/gui.c :: load_weights`、`src/nanogpt.c :: load_corpus`、`src/nanogpt.c :: load_weights`、`src/server.c :: load_corpus`、`src/server.c :: load_weights`

### `cmap_put()`

**调用：** 无（叶子函数）

**被调用：** `src/gui.c :: load_corpus`、`src/gui.c :: load_weights`、`src/nanogpt.c :: load_corpus`、`src/nanogpt.c :: load_weights`、`src/server.c :: load_corpus`、`src/server.c :: load_weights`

### `ctx_append()`

**调用：** `str_to_ids`

**被调用：** `src/ai.c :: ai_mode`、`src/ai.c :: ask_mode`、`src/ai.c :: chat_mode`、`src/gui.c :: ask_mode`、`src/gui.c :: chat_mode`、`src/nanogpt.c :: ask_mode`、`src/nanogpt.c :: chat_mode`、`src/server.c :: ask_mode`、`src/server.c :: chat_mode`、`src/test_answer.c :: ask_mode`、`src/test_answer.c :: chat_mode`

### `e_expr()`

**调用：** `e_skip`、`e_term`

**被调用：** `src/ai.c :: arith_eval`、`src/ai.c :: e_prim`、`src/ai.c :: eval_expr`、`src/gui.c :: arith_eval`、`src/gui.c :: e_prim`、`src/gui.c :: eval_expr`、`src/nanogpt.c :: arith_eval`、`src/nanogpt.c :: e_prim`、`src/nanogpt.c :: eval_expr`、`src/server.c :: arith_eval`、`src/server.c :: e_prim`、`src/server.c :: eval_expr`

### `e_pow()`

**调用：** `e_prim`、`e_skip`、`pow`

**被调用：** `src/ai.c :: e_term`、`src/gui.c :: e_term`、`src/nanogpt.c :: e_term`、`src/server.c :: e_term`、`src/test_answer.c :: e_term`

### `e_prim()`

**调用：** `e_expr`、`e_skip`、`strtod`

**被调用：** `src/ai.c :: e_pow`、`src/gui.c :: e_pow`、`src/nanogpt.c :: e_pow`、`src/server.c :: e_pow`、`src/test_answer.c :: e_pow`

### `e_skip()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: e_expr`、`src/ai.c :: e_pow`、`src/ai.c :: e_prim`、`src/ai.c :: e_term`、`src/gui.c :: e_expr`、`src/gui.c :: e_pow`、`src/gui.c :: e_prim`、`src/gui.c :: e_term`、`src/nanogpt.c :: e_expr`、`src/nanogpt.c :: e_pow`、`src/nanogpt.c :: e_prim`、`src/nanogpt.c :: e_term`

### `e_term()`

**调用：** `e_pow`、`e_skip`

**被调用：** `src/ai.c :: e_expr`、`src/gui.c :: e_expr`、`src/nanogpt.c :: e_expr`、`src/server.c :: e_expr`、`src/test_answer.c :: e_expr`

### `eval_expr()`

**调用：** `e_expr`

**被调用：** `src/ai.c :: ai_mode`、`src/ai.c :: emit`、`src/ai.c :: verify_chain`、`src/gui.c :: answer_q`、`src/gui.c :: emit`、`src/gui.c :: verify_chain`、`src/nanogpt.c :: verify_chain`、`src/server.c :: answer_q`、`src/server.c :: emit`、`src/server.c :: verify_chain`、`src/test_answer.c :: answer_q`、`src/test_answer.c :: emit`

### `eval_loss()`

**调用：** `forward`、`loss_and_grad`、`sample_batch`

**被调用：** `src/ai.c :: train`、`src/gui.c :: train`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: train`、`src/server.c :: train`、`src/test_answer.c :: train`

### `forward()`

**调用：** `collapse`、`expf`、`memset`、`mm_nn`、`rmsnorm_fwd`、`sqrtf`

**被调用：** `src/ai.c :: chat_generate`、`src/ai.c :: eval_loss`、`src/ai.c :: gen_text`、`src/ai.c :: generate`、`src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: chat_generate`、`src/gui.c :: eval_loss`、`src/gui.c :: gen_text`、`src/gui.c :: generate`、`src/gui.c :: gradcheck`、`src/gui.c :: train`

### `frand()`

**调用：** `xrand`

**被调用：** `src/ai.c :: chat_generate`、`src/ai.c :: gen_text`、`src/ai.c :: generate`、`src/ai.c :: gradcheck`、`src/ai.c :: nrand`、`src/gui.c :: chat_generate`、`src/gui.c :: gen_text`、`src/gui.c :: generate`、`src/gui.c :: gradcheck`、`src/gui.c :: nrand`、`src/nanogpt.c :: chat_generate`、`src/nanogpt.c :: gen_text`

### `gen_text()`

**调用：** `expf`、`forward`、`frand`、`id_to_out`、`str_to_ids`

**被调用：** `src/ai.c :: arith_eval`、`src/ai.c :: looks_utf8`、`src/ai.c :: think_mode`、`src/gui.c :: arith_eval`、`src/gui.c :: looks_utf8`、`src/gui.c :: think_mode`、`src/nanogpt.c :: arith_eval`、`src/nanogpt.c :: looks_utf8`、`src/nanogpt.c :: think_mode`、`src/server.c :: arith_eval`、`src/server.c :: looks_utf8`、`src/server.c :: think_mode`

### `generate()`

**调用：** `expf`、`fflush`、`forward`、`frand`、`fwrite`、`id_to_out`、`printf`、`str_to_ids`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`

### `grad_norm()`

**调用：** `sqrt`

**被调用：** `src/ai.c :: adamw_step`、`src/gui.c :: adamw_step`、`src/nanogpt.c :: adamw_step`、`src/nanogpt_dbl.c :: adamw_step`、`src/server.c :: adamw_step`、`src/test_answer.c :: adamw_step`

### `gradcheck()`

**调用：** `alloc_activations`、`backward`、`fabs`、`fabsf`、`forward`、`frand`、`free`、`loss_and_grad`、`malloc`、`printf`、`sample_batch`、`sqrt`、`xrand`、`zero_grads`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`

### `id_to_out()`

**调用：** `u8_put`

**被调用：** `src/gui.c :: chat_generate`、`src/gui.c :: gen_text`、`src/gui.c :: generate`、`src/nanogpt.c :: chat_generate`、`src/nanogpt.c :: gen_text`、`src/nanogpt.c :: generate`、`src/server.c :: chat_generate`、`src/server.c :: gen_text`、`src/server.c :: generate`

### `init_params()`

**调用：** `add_param`、`is_bias`、`memset`、`nrand`、`printf`、`snprintf`、`strcmp`

**被调用：** `src/ai.c :: main`、`src/gui.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`、`src/server.c :: main`、`src/test_answer.c :: main`、`tools/gui_part.c :: main`、`tools/server_part.c :: main`、`tools/test_main.c :: main`

### `is_bias()`

**调用：** `strstr`

**被调用：** `src/ai.c :: init_params`、`src/gui.c :: init_params`、`src/nanogpt.c :: init_params`、`src/nanogpt_dbl.c :: init_params`、`src/server.c :: init_params`、`src/test_answer.c :: init_params`

### `load_corpus()`

**调用：** `char_id`、`cmap_init`、`cmap_put`、`fclose`、`fopen`、`fprintf`、`fread`、`fseek`、`ftell`、`malloc`、`memset`、`printf`、`u8_get`

**被调用：** `src/ai.c :: main`、`src/gui.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`、`src/server.c :: main`、`src/test_answer.c :: main`、`tools/gui_part.c :: main`、`tools/server_part.c :: main`、`tools/test_main.c :: main`

### `load_weights()`

**调用：** `cmap_init`、`cmap_put`、`fclose`、`fopen`、`fprintf`、`fread`、`memcmp`、`printf`、`strncmp`

**被调用：** `src/ai.c :: main`、`src/gui.c :: main`、`src/nanogpt.c :: main`、`src/server.c :: main`、`src/test_answer.c :: main`、`tools/gui_part.c :: main`、`tools/server_part.c :: main`、`tools/test_main.c :: main`

### `looks_utf8()`

**调用：** `MultiByteToWideChar`、`WideCharToMultiByte`、`free`、`gen_text`、`malloc`、`strcpy`、`strlen`、`to_utf8`

**被调用：** `src/test_answer.c :: answer_q`

### `loss_and_grad()`

**调用：** `expf`、`logf`

**被调用：** `src/ai.c :: eval_loss`、`src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: eval_loss`、`src/gui.c :: gradcheck`、`src/gui.c :: train`、`src/nanogpt.c :: eval_loss`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: eval_loss`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: train`

### `main()`

**调用：** `SetConsoleOutputCP`、`alloc_activations`、`arith_eval`、`ask_mode`、`atoi`、`chat_mode`、`fprintf`、`free`、`generate`、`gradcheck`、`init_params`、`load_corpus`、`load_weights`、`printf`、`save_weights`、`strcmp`、`strstr`、`think_mode`、`to_utf8`、`train`

**被调用：** 无（入口函数或未被引用）

### `mm_nn()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: forward`、`src/gui.c :: forward`、`src/nanogpt.c :: forward`、`src/nanogpt_dbl.c :: forward`、`src/server.c :: forward`、`src/test_answer.c :: forward`

### `mm_nt()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: backward`、`src/gui.c :: backward`、`src/nanogpt.c :: backward`、`src/nanogpt_dbl.c :: backward`、`src/server.c :: backward`、`src/test_answer.c :: backward`

### `mm_tn()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: backward`、`src/gui.c :: backward`、`src/nanogpt.c :: backward`、`src/nanogpt_dbl.c :: backward`、`src/server.c :: backward`、`src/test_answer.c :: backward`

### `nrand()`

**调用：** `_Pragma`、`cosf`、`frand`、`logf`、`sqrtf`

**被调用：** `src/ai.c :: init_params`、`src/gui.c :: init_params`、`src/nanogpt.c :: init_params`、`src/nanogpt_dbl.c :: init_params`、`src/server.c :: init_params`、`src/test_answer.c :: init_params`

### `rmsnorm_bwd()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: backward`、`src/gui.c :: backward`、`src/nanogpt.c :: backward`、`src/nanogpt_dbl.c :: backward`、`src/server.c :: backward`、`src/test_answer.c :: backward`

### `rmsnorm_fwd()`

**调用：** `sqrtf`

**被调用：** `src/ai.c :: forward`、`src/gui.c :: forward`、`src/nanogpt.c :: forward`、`src/nanogpt_dbl.c :: forward`、`src/server.c :: forward`、`src/test_answer.c :: forward`

### `sample_batch()`

**调用：** `xrand`

**被调用：** `src/ai.c :: eval_loss`、`src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: eval_loss`、`src/gui.c :: gradcheck`、`src/gui.c :: train`、`src/nanogpt.c :: eval_loss`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: eval_loss`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: train`

### `save_weights()`

**调用：** `fclose`、`fopen`、`fprintf`、`fwrite`、`memset`、`printf`、`strncpy`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`

### `str_to_ids()`

**调用：** `char_id`、`u8_get`

**被调用：** `src/gui.c :: chat_generate`、`src/gui.c :: ctx_append`、`src/gui.c :: gen_text`、`src/gui.c :: generate`、`src/nanogpt.c :: chat_generate`、`src/nanogpt.c :: ctx_append`、`src/nanogpt.c :: gen_text`、`src/nanogpt.c :: generate`、`src/server.c :: chat_generate`、`src/server.c :: ctx_append`、`src/server.c :: gen_text`、`src/server.c :: generate`

### `think_mode()`

**调用：** `gen_text`、`memset`、`printf`、`snprintf`、`strcspn`、`verify_chain`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`

### `train()`

**调用：** `adamw_step`、`backward`、`clock`、`cosf`、`eval_loss`、`fflush`、`forward`、`loss_and_grad`、`printf`、`sample_batch`、`zero_grads`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`、`tools/train_lora.py :: main`

### `u8_get()`

**调用：** 无（叶子函数）

**被调用：** `src/gui.c :: load_corpus`、`src/gui.c :: str_to_ids`、`src/nanogpt.c :: load_corpus`、`src/nanogpt.c :: str_to_ids`、`src/server.c :: load_corpus`、`src/server.c :: str_to_ids`

### `u8_put()`

**调用：** 无（叶子函数）

**被调用：** `src/gui.c :: id_to_out`、`src/nanogpt.c :: id_to_out`、`src/server.c :: id_to_out`

### `verify_chain()`

**调用：** `atof`、`eval_expr`、`fabs`、`fmax`、`isnan`、`memcpy`、`memset`、`strchr`、`strlen`、`strrchr`、`strstr`

**被调用：** `src/ai.c :: think_mode`、`src/gui.c :: think_mode`、`src/nanogpt.c :: think_mode`、`src/server.c :: think_mode`、`src/test_answer.c :: think_mode`

### `xrand()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: frand`、`src/ai.c :: gradcheck`、`src/ai.c :: sample_batch`、`src/gui.c :: frand`、`src/gui.c :: gradcheck`、`src/gui.c :: sample_batch`、`src/nanogpt.c :: frand`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: sample_batch`、`src/nanogpt_dbl.c :: frand`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: sample_batch`

### `zero_grads()`

**调用：** `memset`

**被调用：** `src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: gradcheck`、`src/gui.c :: train`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: train`、`src/server.c :: gradcheck`、`src/server.c :: train`、`src/test_answer.c :: gradcheck`、`src/test_answer.c :: train`

---

## `src/nanogpt_dbl.c`

### `adamw_step()`

**调用：** `SQRT`、`grad_norm`、`powf`

**被调用：** `src/ai.c :: train`、`src/gui.c :: train`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: train`、`src/server.c :: train`、`src/test_answer.c :: train`

### `alloc_activations()`

**调用：** `calloc`、`falloc`

**被调用：** `src/ai.c :: gradcheck`、`src/ai.c :: main`、`src/gui.c :: gradcheck`、`src/gui.c :: main`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: main`、`src/server.c :: gradcheck`、`src/server.c :: main`、`src/test_answer.c :: gradcheck`、`src/test_answer.c :: main`

### `backward()`

**调用：** `SQRT`、`collapse`、`memcpy`、`memset`、`mm_nt`、`mm_tn`、`rmsnorm_bwd`

**被调用：** `src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: gradcheck`、`src/gui.c :: train`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: train`、`src/server.c :: gradcheck`、`src/server.c :: train`、`src/test_answer.c :: gradcheck`、`src/test_answer.c :: train`

### `eval_loss()`

**调用：** `forward`、`loss_and_grad`、`sample_batch`

**被调用：** `src/ai.c :: train`、`src/gui.c :: train`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: train`、`src/server.c :: train`、`src/test_answer.c :: train`

### `forward()`

**调用：** `EXP`、`SQRT`、`collapse`、`memset`、`mm_nn`、`rmsnorm_fwd`

**被调用：** `src/ai.c :: chat_generate`、`src/ai.c :: eval_loss`、`src/ai.c :: gen_text`、`src/ai.c :: generate`、`src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: chat_generate`、`src/gui.c :: eval_loss`、`src/gui.c :: gen_text`、`src/gui.c :: generate`、`src/gui.c :: gradcheck`、`src/gui.c :: train`

### `frand()`

**调用：** `xrand`

**被调用：** `src/ai.c :: chat_generate`、`src/ai.c :: gen_text`、`src/ai.c :: generate`、`src/ai.c :: gradcheck`、`src/ai.c :: nrand`、`src/gui.c :: chat_generate`、`src/gui.c :: gen_text`、`src/gui.c :: generate`、`src/gui.c :: gradcheck`、`src/gui.c :: nrand`、`src/nanogpt.c :: chat_generate`、`src/nanogpt.c :: gen_text`

### `generate()`

**调用：** `EXP`、`fflush`、`forward`、`frand`、`printf`、`putchar`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`

### `grad_norm()`

**调用：** `sqrt`

**被调用：** `src/ai.c :: adamw_step`、`src/gui.c :: adamw_step`、`src/nanogpt.c :: adamw_step`、`src/nanogpt_dbl.c :: adamw_step`、`src/server.c :: adamw_step`、`src/test_answer.c :: adamw_step`

### `gradcheck()`

**调用：** `alloc_activations`、`backward`、`fabs`、`fabsf`、`forward`、`frand`、`free`、`loss_and_grad`、`malloc`、`printf`、`sample_batch`、`sqrt`、`xrand`、`zero_grads`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`

### `init_params()`

**调用：** `add_param`、`is_bias`、`memset`、`nrand`、`printf`、`snprintf`、`strcmp`

**被调用：** `src/ai.c :: main`、`src/gui.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`、`src/server.c :: main`、`src/test_answer.c :: main`、`tools/gui_part.c :: main`、`tools/server_part.c :: main`、`tools/test_main.c :: main`

### `is_bias()`

**调用：** `strstr`

**被调用：** `src/ai.c :: init_params`、`src/gui.c :: init_params`、`src/nanogpt.c :: init_params`、`src/nanogpt_dbl.c :: init_params`、`src/server.c :: init_params`、`src/test_answer.c :: init_params`

### `load_corpus()`

**调用：** `fclose`、`fopen`、`fprintf`、`fread`、`fseek`、`ftell`、`malloc`、`memset`、`printf`

**被调用：** `src/ai.c :: main`、`src/gui.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`、`src/server.c :: main`、`src/test_answer.c :: main`、`tools/gui_part.c :: main`、`tools/server_part.c :: main`、`tools/test_main.c :: main`

### `loss_and_grad()`

**调用：** `EXP`、`LOG`

**被调用：** `src/ai.c :: eval_loss`、`src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: eval_loss`、`src/gui.c :: gradcheck`、`src/gui.c :: train`、`src/nanogpt.c :: eval_loss`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: eval_loss`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: train`

### `main()`

**调用：** `alloc_activations`、`atoi`、`generate`、`gradcheck`、`init_params`、`load_corpus`、`strcmp`、`train`

**被调用：** 无（入口函数或未被引用）

### `mm_nn()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: forward`、`src/gui.c :: forward`、`src/nanogpt.c :: forward`、`src/nanogpt_dbl.c :: forward`、`src/server.c :: forward`、`src/test_answer.c :: forward`

### `mm_nt()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: backward`、`src/gui.c :: backward`、`src/nanogpt.c :: backward`、`src/nanogpt_dbl.c :: backward`、`src/server.c :: backward`、`src/test_answer.c :: backward`

### `mm_tn()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: backward`、`src/gui.c :: backward`、`src/nanogpt.c :: backward`、`src/nanogpt_dbl.c :: backward`、`src/server.c :: backward`、`src/test_answer.c :: backward`

### `nrand()`

**调用：** `COS`、`LOG`、`SQRT`、`_Pragma`、`frand`

**被调用：** `src/ai.c :: init_params`、`src/gui.c :: init_params`、`src/nanogpt.c :: init_params`、`src/nanogpt_dbl.c :: init_params`、`src/server.c :: init_params`、`src/test_answer.c :: init_params`

### `rmsnorm_bwd()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: backward`、`src/gui.c :: backward`、`src/nanogpt.c :: backward`、`src/nanogpt_dbl.c :: backward`、`src/server.c :: backward`、`src/test_answer.c :: backward`

### `rmsnorm_fwd()`

**调用：** `SQRT`

**被调用：** `src/ai.c :: forward`、`src/gui.c :: forward`、`src/nanogpt.c :: forward`、`src/nanogpt_dbl.c :: forward`、`src/server.c :: forward`、`src/test_answer.c :: forward`

### `sample_batch()`

**调用：** `xrand`

**被调用：** `src/ai.c :: eval_loss`、`src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: eval_loss`、`src/gui.c :: gradcheck`、`src/gui.c :: train`、`src/nanogpt.c :: eval_loss`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: eval_loss`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: train`

### `train()`

**调用：** `COS`、`adamw_step`、`backward`、`clock`、`eval_loss`、`fflush`、`forward`、`loss_and_grad`、`printf`、`sample_batch`、`zero_grads`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`、`tools/train_lora.py :: main`

### `xrand()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: frand`、`src/ai.c :: gradcheck`、`src/ai.c :: sample_batch`、`src/gui.c :: frand`、`src/gui.c :: gradcheck`、`src/gui.c :: sample_batch`、`src/nanogpt.c :: frand`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: sample_batch`、`src/nanogpt_dbl.c :: frand`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: sample_batch`

### `zero_grads()`

**调用：** `memset`

**被调用：** `src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: gradcheck`、`src/gui.c :: train`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: train`、`src/server.c :: gradcheck`、`src/server.c :: train`、`src/test_answer.c :: gradcheck`、`src/test_answer.c :: train`

---

## `src/qwen.c`

### `dequant_row()`

**调用：** `die`、`fp16_to_fp32`、`memcpy`

**被调用：** 无（入口函数或未被引用）

### `die()`

**调用：** `exit`、`fprintf`

**被调用：** `src/qwen.c :: dequant_row`、`src/qwen.c :: load_gguf`、`src/qwen.c :: rd`、`src/qwen.c :: read_kv`、`src/qwen.c :: skip_value`

### `fp16_to_fp32()`

**调用：** `memcpy`

**被调用：** `src/qwen.c :: dequant_row`

### `load_gguf()`

**调用：** `die`、`fclose`、`find_tensor`、`fopen`、`fprintf`、`fread`、`free`、`fseek`、`ftell`、`malloc`、`memcmp`、`printf`、`rd`、`rd_gguf_str`、`rd_u32`、`rd_u64`、`read_kv`、`snprintf`、`strcmp`、`type_block_bytes`、`type_block_elems`

**被调用：** `src/qwen.c :: main`

### `main()`

**调用：** `SetConsoleOutputCP`、`find_tensor`、`load_gguf`、`printf`、`type_name`

**被调用：** 无（入口函数或未被引用）

### `rd()`

**调用：** `die`、`fread`

**被调用：** `src/qwen.c :: load_gguf`、`src/qwen.c :: rd_f32`、`src/qwen.c :: rd_f64`、`src/qwen.c :: rd_gguf_str`、`src/qwen.c :: rd_i32`、`src/qwen.c :: rd_u16`、`src/qwen.c :: rd_u32`、`src/qwen.c :: rd_u64`、`src/qwen.c :: rd_u8`

### `rd_f32()`

**调用：** `rd`

**被调用：** `src/qwen.c :: read_kv`

### `rd_f64()`

**调用：** `rd`

**被调用：** `src/qwen.c :: read_kv`、`src/qwen.c :: skip_value`

### `rd_gguf_str()`

**调用：** `malloc`、`rd`、`rd_u64`、`skip_value`

**被调用：** `src/qwen.c :: load_gguf`、`src/qwen.c :: read_array`、`src/qwen.c :: read_kv`、`src/qwen.c :: skip_value`

### `rd_i32()`

**调用：** `rd`

**被调用：** `src/qwen.c :: read_kv`

### `rd_u16()`

**调用：** `rd`

**被调用：** `src/qwen.c :: read_kv`、`src/qwen.c :: skip_value`

### `rd_u32()`

**调用：** `rd`

**被调用：** `src/qwen.c :: load_gguf`、`src/qwen.c :: read_array`、`src/qwen.c :: read_kv`、`src/qwen.c :: skip_value`

### `rd_u64()`

**调用：** `rd`

**被调用：** `src/qwen.c :: load_gguf`、`src/qwen.c :: rd_gguf_str`、`src/qwen.c :: read_array`、`src/qwen.c :: read_kv`、`src/qwen.c :: skip_value`

### `rd_u8()`

**调用：** `rd`

**被调用：** `src/qwen.c :: read_kv`、`src/qwen.c :: skip_value`

### `read_array()`

**调用：** `malloc`、`rd_gguf_str`、`rd_u32`、`rd_u64`、`skip_value`、`strstr`

**被调用：** `src/qwen.c :: read_kv`

### `read_kv()`

**调用：** `die`、`free`、`rd_f32`、`rd_f64`、`rd_gguf_str`、`rd_i32`、`rd_u16`、`rd_u32`、`rd_u64`、`rd_u8`、`read_array`、`snprintf`、`strcmp`、`strstr`

**被调用：** `src/qwen.c :: load_gguf`

### `skip_value()`

**调用：** `die`、`free`、`rd_f64`、`rd_gguf_str`、`rd_u16`、`rd_u32`、`rd_u64`、`rd_u8`

**被调用：** `src/qwen.c :: rd_gguf_str`、`src/qwen.c :: read_array`

### `type_block_bytes()`

**调用：** `type_name`

**被调用：** `src/qwen.c :: load_gguf`

### `type_block_elems()`

**调用：** 无（叶子函数）

**被调用：** `src/qwen.c :: load_gguf`

---

## `src/server.c`

### `abs_path()`

**调用：** `_getcwd`、`snprintf`

**被调用：** `src/gui.c :: answer_q`、`src/server.c :: load_sessions`

### `adamw_step()`

**调用：** `grad_norm`、`powf`、`sqrtf`

**被调用：** `src/ai.c :: train`、`src/gui.c :: train`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: train`、`src/server.c :: train`、`src/test_answer.c :: train`

### `alloc_activations()`

**调用：** `calloc`、`falloc`

**被调用：** `src/ai.c :: gradcheck`、`src/ai.c :: main`、`src/gui.c :: gradcheck`、`src/gui.c :: main`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: main`、`src/server.c :: gradcheck`、`src/server.c :: main`、`src/test_answer.c :: gradcheck`、`src/test_answer.c :: main`

### `answer_q()`

**调用：** `chat_reply`、`eval_expr`、`is_arith_s`、`isnan`、`snprintf`、`solve_linear`、`strchr`、`try_rules`

**被调用：** `src/gui.c :: do_send`、`src/server.c :: load_sessions`、`src/test_answer.c :: main`、`tools/gui_part.c :: do_send`、`tools/server_part.c :: load_sessions`、`tools/test_main.c :: main`

### `arith_eval()`

**调用：** `e_expr`、`fclose`、`fgets`、`fopen`、`gen_text`、`printf`、`snprintf`、`sscanf`、`strtol`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`

### `ask_mode()`

**调用：** `chat_generate`、`ctx_append`、`printf`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`

### `backward()`

**调用：** `collapse`、`memcpy`、`memset`、`mm_nt`、`mm_tn`、`rmsnorm_bwd`、`sqrtf`

**被调用：** `src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: gradcheck`、`src/gui.c :: train`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: train`、`src/server.c :: gradcheck`、`src/server.c :: train`、`src/test_answer.c :: gradcheck`、`src/test_answer.c :: train`

### `char_id()`

**调用：** 无（叶子函数）

**被调用：** `src/gui.c :: load_corpus`、`src/gui.c :: str_to_ids`、`src/nanogpt.c :: load_corpus`、`src/nanogpt.c :: str_to_ids`、`src/server.c :: load_corpus`、`src/server.c :: str_to_ids`

### `chat_generate()`

**调用：** `expf`、`fflush`、`forward`、`frand`、`fwrite`、`id_to_out`、`str_to_ids`

**被调用：** `src/ai.c :: ai_mode`、`src/ai.c :: ask_mode`、`src/ai.c :: chat_mode`、`src/gui.c :: ask_mode`、`src/gui.c :: chat_mode`、`src/nanogpt.c :: ask_mode`、`src/nanogpt.c :: chat_mode`、`src/server.c :: ask_mode`、`src/server.c :: chat_mode`、`src/test_answer.c :: ask_mode`、`src/test_answer.c :: chat_mode`

### `chat_mode()`

**调用：** `chat_generate`、`ctx_append`、`fflush`、`fgets`、`memmove`、`printf`、`strcmp`、`strcspn`、`strncpy`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`

### `chat_reply()`

**调用：** `has`、`localtime`、`pick_reply`、`repf`、`strlen`、`time`

**被调用：** `src/ai.c :: ai_mode`、`src/gui.c :: answer_q`、`src/server.c :: answer_q`、`src/solver.c :: handle`、`src/test_answer.c :: answer_q`、`tools/gui_part.c :: answer_q`、`tools/server_part.c :: answer_q`

### `cmap_init()`

**调用：** 无（叶子函数）

**被调用：** `src/gui.c :: load_corpus`、`src/gui.c :: load_weights`、`src/nanogpt.c :: load_corpus`、`src/nanogpt.c :: load_weights`、`src/server.c :: load_corpus`、`src/server.c :: load_weights`

### `cmap_put()`

**调用：** 无（叶子函数）

**被调用：** `src/gui.c :: load_corpus`、`src/gui.c :: load_weights`、`src/nanogpt.c :: load_corpus`、`src/nanogpt.c :: load_weights`、`src/server.c :: load_corpus`、`src/server.c :: load_weights`

### `cn_digit()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: collect_numbers`、`src/ai.c :: parse_cn`、`src/gui.c :: collect_numbers`、`src/gui.c :: parse_cn`、`src/server.c :: collect_numbers`、`src/server.c :: parse_cn`、`src/solver.c :: collect_numbers`、`src/solver.c :: parse_cn`、`src/test_answer.c :: collect_numbers`、`src/test_answer.c :: parse_cn`

### `collect_numbers()`

**调用：** `cn_digit`、`parse_cn`、`strtod`、`u8_next`、`u8_prev`

**被调用：** `src/ai.c :: try_rules`、`src/gui.c :: try_rules`、`src/server.c :: try_rules`、`src/solver.c :: try_rules`、`src/test_answer.c :: try_rules`

### `ctx_append()`

**调用：** `str_to_ids`

**被调用：** `src/ai.c :: ai_mode`、`src/ai.c :: ask_mode`、`src/ai.c :: chat_mode`、`src/gui.c :: ask_mode`、`src/gui.c :: chat_mode`、`src/nanogpt.c :: ask_mode`、`src/nanogpt.c :: chat_mode`、`src/server.c :: ask_mode`、`src/server.c :: chat_mode`、`src/test_answer.c :: ask_mode`、`src/test_answer.c :: chat_mode`

### `e_expr()`

**调用：** `e_skip`、`e_term`

**被调用：** `src/ai.c :: arith_eval`、`src/ai.c :: e_prim`、`src/ai.c :: eval_expr`、`src/gui.c :: arith_eval`、`src/gui.c :: e_prim`、`src/gui.c :: eval_expr`、`src/nanogpt.c :: arith_eval`、`src/nanogpt.c :: e_prim`、`src/nanogpt.c :: eval_expr`、`src/server.c :: arith_eval`、`src/server.c :: e_prim`、`src/server.c :: eval_expr`

### `e_pow()`

**调用：** `e_prim`、`e_skip`、`pow`

**被调用：** `src/ai.c :: e_term`、`src/gui.c :: e_term`、`src/nanogpt.c :: e_term`、`src/server.c :: e_term`、`src/test_answer.c :: e_term`

### `e_prim()`

**调用：** `e_expr`、`e_skip`、`strtod`

**被调用：** `src/ai.c :: e_pow`、`src/gui.c :: e_pow`、`src/nanogpt.c :: e_pow`、`src/server.c :: e_pow`、`src/test_answer.c :: e_pow`

### `e_skip()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: e_expr`、`src/ai.c :: e_pow`、`src/ai.c :: e_prim`、`src/ai.c :: e_term`、`src/gui.c :: e_expr`、`src/gui.c :: e_pow`、`src/gui.c :: e_prim`、`src/gui.c :: e_term`、`src/nanogpt.c :: e_expr`、`src/nanogpt.c :: e_pow`、`src/nanogpt.c :: e_prim`、`src/nanogpt.c :: e_term`

### `e_term()`

**调用：** `e_pow`、`e_skip`

**被调用：** `src/ai.c :: e_expr`、`src/gui.c :: e_expr`、`src/nanogpt.c :: e_expr`、`src/server.c :: e_expr`、`src/test_answer.c :: e_expr`

### `emit()`

**调用：** `eval_expr`、`isnan`、`repf`

**被调用：** `deploy/stage/agent_r1.py :: do_POST`、`deploy/stage/agent_r1.py :: handle_task`、`deploy/stage/agent_r1.py :: pick_file`、`deploy/stage/serve_r1.py :: do_POST`、`src/ai.c :: try_rules`、`src/gui.c :: try_rules`、`src/server.c :: try_rules`、`src/solver.c :: try_rules`、`src/test_answer.c :: try_rules`、`tools/agent_r1.py :: do_POST`、`tools/agent_r1.py :: handle_task`、`tools/agent_r1.py :: pick_file`

### `eval_expr()`

**调用：** `e_expr`

**被调用：** `src/ai.c :: ai_mode`、`src/ai.c :: emit`、`src/ai.c :: verify_chain`、`src/gui.c :: answer_q`、`src/gui.c :: emit`、`src/gui.c :: verify_chain`、`src/nanogpt.c :: verify_chain`、`src/server.c :: answer_q`、`src/server.c :: emit`、`src/server.c :: verify_chain`、`src/test_answer.c :: answer_q`、`src/test_answer.c :: emit`

### `eval_loss()`

**调用：** `forward`、`loss_and_grad`、`sample_batch`

**被调用：** `src/ai.c :: train`、`src/gui.c :: train`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: train`、`src/server.c :: train`、`src/test_answer.c :: train`

### `first_any()`

**调用：** 无（叶子函数）

**被调用：** 无（入口函数或未被引用）

### `first_of()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: try_rules`、`src/gui.c :: try_rules`、`src/server.c :: try_rules`、`src/solver.c :: try_rules`、`src/test_answer.c :: try_rules`

### `forward()`

**调用：** `collapse`、`expf`、`memset`、`mm_nn`、`rmsnorm_fwd`、`sqrtf`

**被调用：** `src/ai.c :: chat_generate`、`src/ai.c :: eval_loss`、`src/ai.c :: gen_text`、`src/ai.c :: generate`、`src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: chat_generate`、`src/gui.c :: eval_loss`、`src/gui.c :: gen_text`、`src/gui.c :: generate`、`src/gui.c :: gradcheck`、`src/gui.c :: train`

### `frand()`

**调用：** `xrand`

**被调用：** `src/ai.c :: chat_generate`、`src/ai.c :: gen_text`、`src/ai.c :: generate`、`src/ai.c :: gradcheck`、`src/ai.c :: nrand`、`src/gui.c :: chat_generate`、`src/gui.c :: gen_text`、`src/gui.c :: generate`、`src/gui.c :: gradcheck`、`src/gui.c :: nrand`、`src/nanogpt.c :: chat_generate`、`src/nanogpt.c :: gen_text`

### `fs_exec()`

**调用：** `_mkdir`、`fclose`、`fopen`、`fwrite`、`remove`、`snprintf`、`strcmp`

**被调用：** `src/gui.c :: answer_q`

### `gen_text()`

**调用：** `expf`、`forward`、`frand`、`id_to_out`、`str_to_ids`

**被调用：** `src/ai.c :: arith_eval`、`src/ai.c :: looks_utf8`、`src/ai.c :: think_mode`、`src/gui.c :: arith_eval`、`src/gui.c :: looks_utf8`、`src/gui.c :: think_mode`、`src/nanogpt.c :: arith_eval`、`src/nanogpt.c :: looks_utf8`、`src/nanogpt.c :: think_mode`、`src/server.c :: arith_eval`、`src/server.c :: looks_utf8`、`src/server.c :: think_mode`

### `generate()`

**调用：** `expf`、`fflush`、`forward`、`frand`、`fwrite`、`id_to_out`、`printf`、`str_to_ids`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`

### `grad_norm()`

**调用：** `sqrt`

**被调用：** `src/ai.c :: adamw_step`、`src/gui.c :: adamw_step`、`src/nanogpt.c :: adamw_step`、`src/nanogpt_dbl.c :: adamw_step`、`src/server.c :: adamw_step`、`src/test_answer.c :: adamw_step`

### `gradcheck()`

**调用：** `alloc_activations`、`backward`、`fabs`、`fabsf`、`forward`、`frand`、`free`、`loss_and_grad`、`malloc`、`printf`、`sample_batch`、`sqrt`、`xrand`、`zero_grads`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`

### `has()`

**调用：** `strstr`

**被调用：** `src/ai.c :: chat_reply`、`src/ai.c :: try_rules`、`src/gui.c :: chat_reply`、`src/gui.c :: try_rules`、`src/server.c :: chat_reply`、`src/server.c :: try_rules`、`src/solver.c :: chat_reply`、`src/solver.c :: try_rules`、`src/test_answer.c :: chat_reply`、`src/test_answer.c :: try_rules`

### `id_to_out()`

**调用：** `u8_put`

**被调用：** `src/gui.c :: chat_generate`、`src/gui.c :: gen_text`、`src/gui.c :: generate`、`src/nanogpt.c :: chat_generate`、`src/nanogpt.c :: gen_text`、`src/nanogpt.c :: generate`、`src/server.c :: chat_generate`、`src/server.c :: gen_text`、`src/server.c :: generate`

### `init_params()`

**调用：** `add_param`、`is_bias`、`memset`、`nrand`、`printf`、`snprintf`、`strcmp`

**被调用：** `src/ai.c :: main`、`src/gui.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`、`src/server.c :: main`、`src/test_answer.c :: main`、`tools/gui_part.c :: main`、`tools/server_part.c :: main`、`tools/test_main.c :: main`

### `is_arith_s()`

**调用：** `isdigit`、`strchr`

**被调用：** `src/ai.c :: ai_mode`、`src/gui.c :: answer_q`、`src/server.c :: answer_q`、`src/test_answer.c :: answer_q`、`tools/gui_part.c :: answer_q`、`tools/server_part.c :: answer_q`

### `is_bias()`

**调用：** `strstr`

**被调用：** `src/ai.c :: init_params`、`src/gui.c :: init_params`、`src/nanogpt.c :: init_params`、`src/nanogpt_dbl.c :: init_params`、`src/server.c :: init_params`、`src/test_answer.c :: init_params`

### `load_corpus()`

**调用：** `char_id`、`cmap_init`、`cmap_put`、`fclose`、`fopen`、`fprintf`、`fread`、`fseek`、`ftell`、`malloc`、`memset`、`printf`、`u8_get`

**被调用：** `src/ai.c :: main`、`src/gui.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`、`src/server.c :: main`、`src/test_answer.c :: main`、`tools/gui_part.c :: main`、`tools/server_part.c :: main`、`tools/test_main.c :: main`

### `load_sessions()`

**调用：** `ShellExecuteA`、`_mkdir`、`abs_path`、`answer_q`、`closesocket`、`fclose`、`fflush`、`find_session`、`fopen`、`fprintf`、`fread`、`free`、`http_send`、`json_escape`、`json_get`、`malloc`、`memcpy`、`new_session`、`parse_fs_intent`、`pend_clear`、`sess_append_log`、`snprintf`、`strcmp`、`strcpy`、`strlen`、`strncmp`、`strstr`、`u8_count`

**被调用：** `deploy/stage/serve_r1.py :: main`、`src/server.c :: main`、`tools/serve_r1.py :: main`、`tools/server_part.c :: main`

### `load_weights()`

**调用：** `cmap_init`、`cmap_put`、`fclose`、`fopen`、`fprintf`、`fread`、`memcmp`、`printf`、`strncmp`

**被调用：** `src/ai.c :: main`、`src/gui.c :: main`、`src/nanogpt.c :: main`、`src/server.c :: main`、`src/test_answer.c :: main`、`tools/gui_part.c :: main`、`tools/server_part.c :: main`、`tools/test_main.c :: main`

### `looks_utf8()`

**调用：** `MultiByteToWideChar`、`WideCharToMultiByte`、`free`、`gen_text`、`malloc`、`strcpy`、`strlen`、`to_utf8`

**被调用：** `src/test_answer.c :: answer_q`

### `loss_and_grad()`

**调用：** `expf`、`logf`

**被调用：** `src/ai.c :: eval_loss`、`src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: eval_loss`、`src/gui.c :: gradcheck`、`src/gui.c :: train`、`src/nanogpt.c :: eval_loss`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: eval_loss`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: train`

### `main()`

**调用：** `SetConsoleOutputCP`、`alloc_activations`、`atoi`、`fprintf`、`init_params`、`load_corpus`、`load_sessions`、`load_weights`、`serve`

**被调用：** 无（入口函数或未被引用）

### `max_num()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: try_rules`、`src/gui.c :: try_rules`、`src/server.c :: try_rules`、`src/solver.c :: try_rules`、`src/test_answer.c :: try_rules`

### `mm_nn()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: forward`、`src/gui.c :: forward`、`src/nanogpt.c :: forward`、`src/nanogpt_dbl.c :: forward`、`src/server.c :: forward`、`src/test_answer.c :: forward`

### `mm_nt()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: backward`、`src/gui.c :: backward`、`src/nanogpt.c :: backward`、`src/nanogpt_dbl.c :: backward`、`src/server.c :: backward`、`src/test_answer.c :: backward`

### `mm_tn()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: backward`、`src/gui.c :: backward`、`src/nanogpt.c :: backward`、`src/nanogpt_dbl.c :: backward`、`src/server.c :: backward`、`src/test_answer.c :: backward`

### `nrand()`

**调用：** `_Pragma`、`cosf`、`frand`、`logf`、`sqrtf`

**被调用：** `src/ai.c :: init_params`、`src/gui.c :: init_params`、`src/nanogpt.c :: init_params`、`src/nanogpt_dbl.c :: init_params`、`src/server.c :: init_params`、`src/test_answer.c :: init_params`

### `parse_cn()`

**调用：** `cn_digit`、`u8_next`

**被调用：** `src/ai.c :: collect_numbers`、`src/gui.c :: collect_numbers`、`src/server.c :: collect_numbers`、`src/solver.c :: collect_numbers`、`src/test_answer.c :: collect_numbers`

### `parse_fs_intent()`

**调用：** `snprintf`、`strlen`、`strstr`

**被调用：** `src/gui.c :: answer_q`、`src/server.c :: load_sessions`

### `pend_clear()`

**调用：** `free`

**被调用：** `src/server.c :: load_sessions`

### `rep()`

**调用：** `memcpy`、`strlen`

**被调用：** `src/gui.c :: repf`、`src/server.c :: repf`、`src/test_answer.c :: repf`、`tools/gui_part.c :: repf`、`tools/server_part.c :: repf`

### `repf()`

**调用：** `rep`、`va_end`、`va_start`、`vsnprintf`

**被调用：** `src/gui.c :: chat_reply`、`src/gui.c :: emit`、`src/server.c :: chat_reply`、`src/server.c :: emit`、`src/test_answer.c :: chat_reply`、`src/test_answer.c :: emit`

### `rmsnorm_bwd()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: backward`、`src/gui.c :: backward`、`src/nanogpt.c :: backward`、`src/nanogpt_dbl.c :: backward`、`src/server.c :: backward`、`src/test_answer.c :: backward`

### `rmsnorm_fwd()`

**调用：** `sqrtf`

**被调用：** `src/ai.c :: forward`、`src/gui.c :: forward`、`src/nanogpt.c :: forward`、`src/nanogpt_dbl.c :: forward`、`src/server.c :: forward`、`src/test_answer.c :: forward`

### `sample_batch()`

**调用：** `xrand`

**被调用：** `src/ai.c :: eval_loss`、`src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: eval_loss`、`src/gui.c :: gradcheck`、`src/gui.c :: train`、`src/nanogpt.c :: eval_loss`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: eval_loss`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: train`

### `save_weights()`

**调用：** `fclose`、`fopen`、`fprintf`、`fwrite`、`memset`、`printf`、`strncpy`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`

### `sess_append_log()`

**调用：** `fclose`、`find_session`、`fopen`、`fwrite`、`malloc`、`memcpy`、`new_session`、`realloc`、`snprintf`、`strcmp`、`strlen`

**被调用：** `src/server.c :: load_sessions`、`tools/server_part.c :: load_sessions`

### `solve_linear()`

**调用：** `fabs`、`lin_term`、`snprintf`、`strchr`

**被调用：** `src/ai.c :: ai_mode`、`src/gui.c :: answer_q`、`src/server.c :: answer_q`、`src/solver.c :: handle`、`src/solver.c :: main`、`src/test_answer.c :: answer_q`、`tools/gui_part.c :: answer_q`、`tools/server_part.c :: answer_q`

### `str_to_ids()`

**调用：** `char_id`、`u8_get`

**被调用：** `src/gui.c :: chat_generate`、`src/gui.c :: ctx_append`、`src/gui.c :: gen_text`、`src/gui.c :: generate`、`src/nanogpt.c :: chat_generate`、`src/nanogpt.c :: ctx_append`、`src/nanogpt.c :: gen_text`、`src/nanogpt.c :: generate`、`src/server.c :: chat_generate`、`src/server.c :: ctx_append`、`src/server.c :: gen_text`、`src/server.c :: generate`

### `think_mode()`

**调用：** `gen_text`、`lin_term`、`memset`、`printf`、`snprintf`、`strcspn`、`verify_chain`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`

### `train()`

**调用：** `adamw_step`、`backward`、`clock`、`cosf`、`eval_loss`、`fflush`、`forward`、`loss_and_grad`、`printf`、`sample_batch`、`zero_grads`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`、`tools/train_lora.py :: main`

### `try_rules()`

**调用：** `collect_numbers`、`emit`、`first_of`、`has`、`max_num`、`pick_reply`、`snprintf`、`strlen`、`strncat`

**被调用：** `src/ai.c :: ai_mode`、`src/gui.c :: answer_q`、`src/server.c :: answer_q`、`src/solver.c :: handle`、`src/test_answer.c :: answer_q`、`tools/gui_part.c :: answer_q`、`tools/server_part.c :: answer_q`

### `u8_count()`

**调用：** 无（叶子函数）

**被调用：** `src/gui.c :: do_send`、`src/server.c :: load_sessions`

### `u8_get()`

**调用：** 无（叶子函数）

**被调用：** `src/gui.c :: load_corpus`、`src/gui.c :: str_to_ids`、`src/nanogpt.c :: load_corpus`、`src/nanogpt.c :: str_to_ids`、`src/server.c :: load_corpus`、`src/server.c :: str_to_ids`

### `u8_next()`

**调用：** `u8_prev`

**被调用：** `src/ai.c :: collect_numbers`、`src/ai.c :: parse_cn`、`src/gui.c :: collect_numbers`、`src/gui.c :: parse_cn`、`src/server.c :: collect_numbers`、`src/server.c :: parse_cn`、`src/solver.c :: collect_numbers`、`src/solver.c :: parse_cn`、`src/test_answer.c :: collect_numbers`、`src/test_answer.c :: parse_cn`

### `u8_put()`

**调用：** 无（叶子函数）

**被调用：** `src/gui.c :: id_to_out`、`src/nanogpt.c :: id_to_out`、`src/server.c :: id_to_out`

### `verify_chain()`

**调用：** `atof`、`eval_expr`、`fabs`、`fmax`、`isnan`、`memcpy`、`memset`、`strchr`、`strlen`、`strrchr`、`strstr`

**被调用：** `src/ai.c :: think_mode`、`src/gui.c :: think_mode`、`src/nanogpt.c :: think_mode`、`src/server.c :: think_mode`、`src/test_answer.c :: think_mode`

### `xrand()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: frand`、`src/ai.c :: gradcheck`、`src/ai.c :: sample_batch`、`src/gui.c :: frand`、`src/gui.c :: gradcheck`、`src/gui.c :: sample_batch`、`src/nanogpt.c :: frand`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: sample_batch`、`src/nanogpt_dbl.c :: frand`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: sample_batch`

### `zero_grads()`

**调用：** `memset`

**被调用：** `src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: gradcheck`、`src/gui.c :: train`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: train`、`src/server.c :: gradcheck`、`src/server.c :: train`、`src/test_answer.c :: gradcheck`、`src/test_answer.c :: train`

---

## `src/solver.c`

### `build_index()`

**调用：** `calloc`、`fprintf`、`malloc`、`tri`

**被调用：** `deploy/package/worker.py :: main`、`deploy/stage/serve_r1.py :: main`、`deploy/stage/worker.py :: main`、`deploy/worker.py :: main`、`src/solver.c :: main`、`tools/serve_r1.py :: main`

### `chat_reply()`

**调用：** `has`、`localtime`、`pick_reply`、`printf`、`strlen`、`time`

**被调用：** `src/ai.c :: ai_mode`、`src/gui.c :: answer_q`、`src/server.c :: answer_q`、`src/solver.c :: handle`、`src/test_answer.c :: answer_q`、`tools/gui_part.c :: answer_q`、`tools/server_part.c :: answer_q`

### `cn_digit()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: collect_numbers`、`src/ai.c :: parse_cn`、`src/gui.c :: collect_numbers`、`src/gui.c :: parse_cn`、`src/server.c :: collect_numbers`、`src/server.c :: parse_cn`、`src/solver.c :: collect_numbers`、`src/solver.c :: parse_cn`、`src/test_answer.c :: collect_numbers`、`src/test_answer.c :: parse_cn`

### `collect_numbers()`

**调用：** `cn_digit`、`parse_cn`、`strtod`、`u8_next`、`u8_prev`

**被调用：** `src/ai.c :: try_rules`、`src/gui.c :: try_rules`、`src/server.c :: try_rules`、`src/solver.c :: try_rules`、`src/test_answer.c :: try_rules`

### `emit()`

**调用：** `eval_arith`、`isnan`、`printf`

**被调用：** `deploy/stage/agent_r1.py :: do_POST`、`deploy/stage/agent_r1.py :: handle_task`、`deploy/stage/agent_r1.py :: pick_file`、`deploy/stage/serve_r1.py :: do_POST`、`src/ai.c :: try_rules`、`src/gui.c :: try_rules`、`src/server.c :: try_rules`、`src/solver.c :: try_rules`、`src/test_answer.c :: try_rules`、`tools/agent_r1.py :: do_POST`、`tools/agent_r1.py :: handle_task`、`tools/agent_r1.py :: pick_file`

### `eval_arith()`

**调用：** `lin_term`、`p_expr`

**被调用：** `src/solver.c :: emit`、`src/solver.c :: handle`、`src/solver.c :: main`

### `first_any()`

**调用：** 无（叶子函数）

**被调用：** 无（入口函数或未被引用）

### `first_of()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: try_rules`、`src/gui.c :: try_rules`、`src/server.c :: try_rules`、`src/solver.c :: try_rules`、`src/test_answer.c :: try_rules`

### `gram_idf()`

**调用：** `log`

**被调用：** `src/solver.c :: query_body`

### `handle()`

**调用：** `chat_reply`、`eval_arith`、`is_arith`、`isnan`、`printf`、`query_body`、`snprintf`、`solve_linear`、`strchr`、`try_rules`

**被调用：** `src/solver.c :: main`

### `has()`

**调用：** `strstr`

**被调用：** `src/ai.c :: chat_reply`、`src/ai.c :: try_rules`、`src/gui.c :: chat_reply`、`src/gui.c :: try_rules`、`src/server.c :: chat_reply`、`src/server.c :: try_rules`、`src/solver.c :: chat_reply`、`src/solver.c :: try_rules`、`src/test_answer.c :: chat_reply`、`src/test_answer.c :: try_rules`

### `index_lines()`

**调用：** `malloc`

**被调用：** `src/solver.c :: main`

### `is_arith()`

**调用：** `isdigit`、`strchr`

**被调用：** `src/solver.c :: handle`

### `load_file()`

**调用：** `fclose`、`fopen`、`fprintf`、`fread`、`fseek`、`ftell`、`malloc`

**被调用：** `src/solver.c :: main`

### `looks_utf8()`

**调用：** `MultiByteToWideChar`、`WideCharToMultiByte`、`free`、`malloc`、`p_expr`、`strcpy`、`strlen`、`to_utf8`

**被调用：** `src/test_answer.c :: answer_q`

### `main()`

**调用：** `SetConsoleOutputCP`、`build_index`、`eval_arith`、`fflush`、`fgets`、`free`、`handle`、`index_lines`、`load_file`、`printf`、`solve_linear`、`strcmp`、`strcspn`、`to_utf8`

**被调用：** 无（入口函数或未被引用）

### `max_num()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: try_rules`、`src/gui.c :: try_rules`、`src/server.c :: try_rules`、`src/solver.c :: try_rules`、`src/test_answer.c :: try_rules`

### `p_expr()`

**调用：** `p_term`、`skipsp`

**被调用：** `src/solver.c :: eval_arith`、`src/solver.c :: looks_utf8`、`src/solver.c :: p_primary`

### `p_power()`

**调用：** `p_primary`、`pow`、`skipsp`

**被调用：** `src/solver.c :: p_term`

### `p_primary()`

**调用：** `p_expr`、`skipsp`、`strtod`

**被调用：** `src/solver.c :: p_power`

### `p_term()`

**调用：** `p_power`、`skipsp`

**被调用：** `src/solver.c :: p_expr`

### `parse_cn()`

**调用：** `cn_digit`、`u8_next`

**被调用：** `src/ai.c :: collect_numbers`、`src/gui.c :: collect_numbers`、`src/server.c :: collect_numbers`、`src/solver.c :: collect_numbers`、`src/test_answer.c :: collect_numbers`

### `query_body()`

**调用：** `gram_idf`、`memset`、`printf`、`sqrt`、`tri`

**被调用：** `src/solver.c :: handle`

### `skipsp()`

**调用：** 无（叶子函数）

**被调用：** `src/solver.c :: p_expr`、`src/solver.c :: p_power`、`src/solver.c :: p_primary`、`src/solver.c :: p_term`

### `solve_linear()`

**调用：** `TMAP`、`fabs`、`lin_term`、`snprintf`、`strchr`

**被调用：** `src/ai.c :: ai_mode`、`src/gui.c :: answer_q`、`src/server.c :: answer_q`、`src/solver.c :: handle`、`src/solver.c :: main`、`src/test_answer.c :: answer_q`、`tools/gui_part.c :: answer_q`、`tools/server_part.c :: answer_q`

### `tri()`

**调用：** 无（叶子函数）

**被调用：** `src/solver.c :: build_index`、`src/solver.c :: query_body`

### `try_rules()`

**调用：** `collect_numbers`、`emit`、`first_of`、`has`、`max_num`、`pick_reply`、`snprintf`、`strlen`、`strncat`

**被调用：** `src/ai.c :: ai_mode`、`src/gui.c :: answer_q`、`src/server.c :: answer_q`、`src/solver.c :: handle`、`src/test_answer.c :: answer_q`、`tools/gui_part.c :: answer_q`、`tools/server_part.c :: answer_q`

### `u8_next()`

**调用：** `u8_prev`

**被调用：** `src/ai.c :: collect_numbers`、`src/ai.c :: parse_cn`、`src/gui.c :: collect_numbers`、`src/gui.c :: parse_cn`、`src/server.c :: collect_numbers`、`src/server.c :: parse_cn`、`src/solver.c :: collect_numbers`、`src/solver.c :: parse_cn`、`src/test_answer.c :: collect_numbers`、`src/test_answer.c :: parse_cn`

---

## `src/test_answer.c`

### `adamw_step()`

**调用：** `grad_norm`、`powf`、`sqrtf`

**被调用：** `src/ai.c :: train`、`src/gui.c :: train`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: train`、`src/server.c :: train`、`src/test_answer.c :: train`

### `alloc_activations()`

**调用：** `calloc`、`falloc`

**被调用：** `src/ai.c :: gradcheck`、`src/ai.c :: main`、`src/gui.c :: gradcheck`、`src/gui.c :: main`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: main`、`src/server.c :: gradcheck`、`src/server.c :: main`、`src/test_answer.c :: gradcheck`、`src/test_answer.c :: main`

### `answer_q()`

**调用：** `chat_reply`、`eval_expr`、`gen_text`、`is_arith_s`、`isnan`、`looks_utf8`、`sess_append`、`snprintf`、`solve_linear`、`strchr`、`strstr`、`try_rules`

**被调用：** `src/gui.c :: do_send`、`src/server.c :: load_sessions`、`src/test_answer.c :: main`、`tools/gui_part.c :: do_send`、`tools/server_part.c :: load_sessions`、`tools/test_main.c :: main`

### `arith_eval()`

**调用：** `e_expr`、`fclose`、`fgets`、`fopen`、`gen_text`、`printf`、`snprintf`、`sscanf`、`strtol`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`

### `ask_mode()`

**调用：** `chat_generate`、`ctx_append`、`printf`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`

### `backward()`

**调用：** `collapse`、`memcpy`、`memset`、`mm_nt`、`mm_tn`、`rmsnorm_bwd`、`sqrtf`

**被调用：** `src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: gradcheck`、`src/gui.c :: train`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: train`、`src/server.c :: gradcheck`、`src/server.c :: train`、`src/test_answer.c :: gradcheck`、`src/test_answer.c :: train`

### `chat_generate()`

**调用：** `expf`、`fflush`、`forward`、`frand`、`putchar`、`strlen`

**被调用：** `src/ai.c :: ai_mode`、`src/ai.c :: ask_mode`、`src/ai.c :: chat_mode`、`src/gui.c :: ask_mode`、`src/gui.c :: chat_mode`、`src/nanogpt.c :: ask_mode`、`src/nanogpt.c :: chat_mode`、`src/server.c :: ask_mode`、`src/server.c :: chat_mode`、`src/test_answer.c :: ask_mode`、`src/test_answer.c :: chat_mode`

### `chat_mode()`

**调用：** `chat_generate`、`ctx_append`、`fflush`、`fgets`、`memmove`、`printf`、`strcmp`、`strcspn`、`strncpy`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`

### `chat_reply()`

**调用：** `has`、`localtime`、`pick_reply`、`repf`、`strlen`、`time`

**被调用：** `src/ai.c :: ai_mode`、`src/gui.c :: answer_q`、`src/server.c :: answer_q`、`src/solver.c :: handle`、`src/test_answer.c :: answer_q`、`tools/gui_part.c :: answer_q`、`tools/server_part.c :: answer_q`

### `cn_digit()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: collect_numbers`、`src/ai.c :: parse_cn`、`src/gui.c :: collect_numbers`、`src/gui.c :: parse_cn`、`src/server.c :: collect_numbers`、`src/server.c :: parse_cn`、`src/solver.c :: collect_numbers`、`src/solver.c :: parse_cn`、`src/test_answer.c :: collect_numbers`、`src/test_answer.c :: parse_cn`

### `collect_numbers()`

**调用：** `cn_digit`、`parse_cn`、`strtod`、`u8_next`、`u8_prev`

**被调用：** `src/ai.c :: try_rules`、`src/gui.c :: try_rules`、`src/server.c :: try_rules`、`src/solver.c :: try_rules`、`src/test_answer.c :: try_rules`

### `ctx_append()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: ai_mode`、`src/ai.c :: ask_mode`、`src/ai.c :: chat_mode`、`src/gui.c :: ask_mode`、`src/gui.c :: chat_mode`、`src/nanogpt.c :: ask_mode`、`src/nanogpt.c :: chat_mode`、`src/server.c :: ask_mode`、`src/server.c :: chat_mode`、`src/test_answer.c :: ask_mode`、`src/test_answer.c :: chat_mode`

### `e_expr()`

**调用：** `e_skip`、`e_term`

**被调用：** `src/ai.c :: arith_eval`、`src/ai.c :: e_prim`、`src/ai.c :: eval_expr`、`src/gui.c :: arith_eval`、`src/gui.c :: e_prim`、`src/gui.c :: eval_expr`、`src/nanogpt.c :: arith_eval`、`src/nanogpt.c :: e_prim`、`src/nanogpt.c :: eval_expr`、`src/server.c :: arith_eval`、`src/server.c :: e_prim`、`src/server.c :: eval_expr`

### `e_pow()`

**调用：** `e_prim`、`e_skip`、`pow`

**被调用：** `src/ai.c :: e_term`、`src/gui.c :: e_term`、`src/nanogpt.c :: e_term`、`src/server.c :: e_term`、`src/test_answer.c :: e_term`

### `e_prim()`

**调用：** `e_expr`、`e_skip`、`strtod`

**被调用：** `src/ai.c :: e_pow`、`src/gui.c :: e_pow`、`src/nanogpt.c :: e_pow`、`src/server.c :: e_pow`、`src/test_answer.c :: e_pow`

### `e_skip()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: e_expr`、`src/ai.c :: e_pow`、`src/ai.c :: e_prim`、`src/ai.c :: e_term`、`src/gui.c :: e_expr`、`src/gui.c :: e_pow`、`src/gui.c :: e_prim`、`src/gui.c :: e_term`、`src/nanogpt.c :: e_expr`、`src/nanogpt.c :: e_pow`、`src/nanogpt.c :: e_prim`、`src/nanogpt.c :: e_term`

### `e_term()`

**调用：** `e_pow`、`e_skip`

**被调用：** `src/ai.c :: e_expr`、`src/gui.c :: e_expr`、`src/nanogpt.c :: e_expr`、`src/server.c :: e_expr`、`src/test_answer.c :: e_expr`

### `emit()`

**调用：** `eval_expr`、`isnan`、`repf`

**被调用：** `deploy/stage/agent_r1.py :: do_POST`、`deploy/stage/agent_r1.py :: handle_task`、`deploy/stage/agent_r1.py :: pick_file`、`deploy/stage/serve_r1.py :: do_POST`、`src/ai.c :: try_rules`、`src/gui.c :: try_rules`、`src/server.c :: try_rules`、`src/solver.c :: try_rules`、`src/test_answer.c :: try_rules`、`tools/agent_r1.py :: do_POST`、`tools/agent_r1.py :: handle_task`、`tools/agent_r1.py :: pick_file`

### `eval_expr()`

**调用：** `e_expr`

**被调用：** `src/ai.c :: ai_mode`、`src/ai.c :: emit`、`src/ai.c :: verify_chain`、`src/gui.c :: answer_q`、`src/gui.c :: emit`、`src/gui.c :: verify_chain`、`src/nanogpt.c :: verify_chain`、`src/server.c :: answer_q`、`src/server.c :: emit`、`src/server.c :: verify_chain`、`src/test_answer.c :: answer_q`、`src/test_answer.c :: emit`

### `eval_loss()`

**调用：** `forward`、`loss_and_grad`、`sample_batch`

**被调用：** `src/ai.c :: train`、`src/gui.c :: train`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: train`、`src/server.c :: train`、`src/test_answer.c :: train`

### `first_any()`

**调用：** 无（叶子函数）

**被调用：** 无（入口函数或未被引用）

### `first_of()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: try_rules`、`src/gui.c :: try_rules`、`src/server.c :: try_rules`、`src/solver.c :: try_rules`、`src/test_answer.c :: try_rules`

### `forward()`

**调用：** `collapse`、`expf`、`memset`、`mm_nn`、`rmsnorm_fwd`、`sqrtf`

**被调用：** `src/ai.c :: chat_generate`、`src/ai.c :: eval_loss`、`src/ai.c :: gen_text`、`src/ai.c :: generate`、`src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: chat_generate`、`src/gui.c :: eval_loss`、`src/gui.c :: gen_text`、`src/gui.c :: generate`、`src/gui.c :: gradcheck`、`src/gui.c :: train`

### `frand()`

**调用：** `xrand`

**被调用：** `src/ai.c :: chat_generate`、`src/ai.c :: gen_text`、`src/ai.c :: generate`、`src/ai.c :: gradcheck`、`src/ai.c :: nrand`、`src/gui.c :: chat_generate`、`src/gui.c :: gen_text`、`src/gui.c :: generate`、`src/gui.c :: gradcheck`、`src/gui.c :: nrand`、`src/nanogpt.c :: chat_generate`、`src/nanogpt.c :: gen_text`

### `gen_text()`

**调用：** `expf`、`forward`、`frand`

**被调用：** `src/ai.c :: arith_eval`、`src/ai.c :: looks_utf8`、`src/ai.c :: think_mode`、`src/gui.c :: arith_eval`、`src/gui.c :: looks_utf8`、`src/gui.c :: think_mode`、`src/nanogpt.c :: arith_eval`、`src/nanogpt.c :: looks_utf8`、`src/nanogpt.c :: think_mode`、`src/server.c :: arith_eval`、`src/server.c :: looks_utf8`、`src/server.c :: think_mode`

### `generate()`

**调用：** `expf`、`fflush`、`forward`、`frand`、`printf`、`putchar`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`

### `grad_norm()`

**调用：** `sqrt`

**被调用：** `src/ai.c :: adamw_step`、`src/gui.c :: adamw_step`、`src/nanogpt.c :: adamw_step`、`src/nanogpt_dbl.c :: adamw_step`、`src/server.c :: adamw_step`、`src/test_answer.c :: adamw_step`

### `gradcheck()`

**调用：** `alloc_activations`、`backward`、`fabs`、`fabsf`、`forward`、`frand`、`free`、`loss_and_grad`、`malloc`、`printf`、`sample_batch`、`sqrt`、`xrand`、`zero_grads`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`

### `has()`

**调用：** `strstr`

**被调用：** `src/ai.c :: chat_reply`、`src/ai.c :: try_rules`、`src/gui.c :: chat_reply`、`src/gui.c :: try_rules`、`src/server.c :: chat_reply`、`src/server.c :: try_rules`、`src/solver.c :: chat_reply`、`src/solver.c :: try_rules`、`src/test_answer.c :: chat_reply`、`src/test_answer.c :: try_rules`

### `init_params()`

**调用：** `add_param`、`is_bias`、`memset`、`nrand`、`printf`、`snprintf`、`strcmp`

**被调用：** `src/ai.c :: main`、`src/gui.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`、`src/server.c :: main`、`src/test_answer.c :: main`、`tools/gui_part.c :: main`、`tools/server_part.c :: main`、`tools/test_main.c :: main`

### `is_arith_s()`

**调用：** `isdigit`、`strchr`

**被调用：** `src/ai.c :: ai_mode`、`src/gui.c :: answer_q`、`src/server.c :: answer_q`、`src/test_answer.c :: answer_q`、`tools/gui_part.c :: answer_q`、`tools/server_part.c :: answer_q`

### `is_bias()`

**调用：** `strstr`

**被调用：** `src/ai.c :: init_params`、`src/gui.c :: init_params`、`src/nanogpt.c :: init_params`、`src/nanogpt_dbl.c :: init_params`、`src/server.c :: init_params`、`src/test_answer.c :: init_params`

### `load_corpus()`

**调用：** `fclose`、`fopen`、`fprintf`、`fread`、`fseek`、`ftell`、`malloc`、`memset`、`printf`

**被调用：** `src/ai.c :: main`、`src/gui.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`、`src/server.c :: main`、`src/test_answer.c :: main`、`tools/gui_part.c :: main`、`tools/server_part.c :: main`、`tools/test_main.c :: main`

### `load_weights()`

**调用：** `fclose`、`fopen`、`fprintf`、`fread`、`memcmp`、`printf`、`strncmp`

**被调用：** `src/ai.c :: main`、`src/gui.c :: main`、`src/nanogpt.c :: main`、`src/server.c :: main`、`src/test_answer.c :: main`、`tools/gui_part.c :: main`、`tools/server_part.c :: main`、`tools/test_main.c :: main`

### `looks_utf8()`

**调用：** `MultiByteToWideChar`、`WideCharToMultiByte`、`free`、`gen_text`、`malloc`、`strcpy`、`strlen`、`to_utf8`

**被调用：** `src/test_answer.c :: answer_q`

### `loss_and_grad()`

**调用：** `expf`、`logf`

**被调用：** `src/ai.c :: eval_loss`、`src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: eval_loss`、`src/gui.c :: gradcheck`、`src/gui.c :: train`、`src/nanogpt.c :: eval_loss`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: eval_loss`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: train`

### `main()`

**调用：** `SetConsoleOutputCP`、`alloc_activations`、`answer_q`、`fflush`、`init_params`、`load_corpus`、`load_weights`、`printf`

**被调用：** 无（入口函数或未被引用）

### `max_num()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: try_rules`、`src/gui.c :: try_rules`、`src/server.c :: try_rules`、`src/solver.c :: try_rules`、`src/test_answer.c :: try_rules`

### `mm_nn()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: forward`、`src/gui.c :: forward`、`src/nanogpt.c :: forward`、`src/nanogpt_dbl.c :: forward`、`src/server.c :: forward`、`src/test_answer.c :: forward`

### `mm_nt()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: backward`、`src/gui.c :: backward`、`src/nanogpt.c :: backward`、`src/nanogpt_dbl.c :: backward`、`src/server.c :: backward`、`src/test_answer.c :: backward`

### `mm_tn()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: backward`、`src/gui.c :: backward`、`src/nanogpt.c :: backward`、`src/nanogpt_dbl.c :: backward`、`src/server.c :: backward`、`src/test_answer.c :: backward`

### `nrand()`

**调用：** `_Pragma`、`cosf`、`frand`、`logf`、`sqrtf`

**被调用：** `src/ai.c :: init_params`、`src/gui.c :: init_params`、`src/nanogpt.c :: init_params`、`src/nanogpt_dbl.c :: init_params`、`src/server.c :: init_params`、`src/test_answer.c :: init_params`

### `parse_cn()`

**调用：** `cn_digit`、`u8_next`

**被调用：** `src/ai.c :: collect_numbers`、`src/gui.c :: collect_numbers`、`src/server.c :: collect_numbers`、`src/solver.c :: collect_numbers`、`src/test_answer.c :: collect_numbers`

### `rep()`

**调用：** `memcpy`、`strlen`

**被调用：** `src/gui.c :: repf`、`src/server.c :: repf`、`src/test_answer.c :: repf`、`tools/gui_part.c :: repf`、`tools/server_part.c :: repf`

### `repf()`

**调用：** `rep`、`va_end`、`va_start`、`vsnprintf`

**被调用：** `src/gui.c :: chat_reply`、`src/gui.c :: emit`、`src/server.c :: chat_reply`、`src/server.c :: emit`、`src/test_answer.c :: chat_reply`、`src/test_answer.c :: emit`

### `rmsnorm_bwd()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: backward`、`src/gui.c :: backward`、`src/nanogpt.c :: backward`、`src/nanogpt_dbl.c :: backward`、`src/server.c :: backward`、`src/test_answer.c :: backward`

### `rmsnorm_fwd()`

**调用：** `sqrtf`

**被调用：** `src/ai.c :: forward`、`src/gui.c :: forward`、`src/nanogpt.c :: forward`、`src/nanogpt_dbl.c :: forward`、`src/server.c :: forward`、`src/test_answer.c :: forward`

### `sample_batch()`

**调用：** `xrand`

**被调用：** `src/ai.c :: eval_loss`、`src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: eval_loss`、`src/gui.c :: gradcheck`、`src/gui.c :: train`、`src/nanogpt.c :: eval_loss`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: eval_loss`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: train`

### `save_weights()`

**调用：** `fclose`、`fopen`、`fprintf`、`fwrite`、`memset`、`printf`、`strncpy`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`

### `sess_append()`

**调用：** `memcpy`、`strlen`

**被调用：** `src/test_answer.c :: answer_q`

### `solve_linear()`

**调用：** `fabs`、`lin_term`、`snprintf`、`strchr`

**被调用：** `src/ai.c :: ai_mode`、`src/gui.c :: answer_q`、`src/server.c :: answer_q`、`src/solver.c :: handle`、`src/solver.c :: main`、`src/test_answer.c :: answer_q`、`tools/gui_part.c :: answer_q`、`tools/server_part.c :: answer_q`

### `think_mode()`

**调用：** `gen_text`、`lin_term`、`memset`、`printf`、`snprintf`、`strcspn`、`verify_chain`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`

### `train()`

**调用：** `adamw_step`、`backward`、`clock`、`cosf`、`eval_loss`、`fflush`、`forward`、`loss_and_grad`、`printf`、`sample_batch`、`zero_grads`

**被调用：** `src/ai.c :: main`、`src/nanogpt.c :: main`、`src/nanogpt_dbl.c :: main`、`tools/train_lora.py :: main`

### `try_rules()`

**调用：** `collect_numbers`、`emit`、`first_of`、`has`、`max_num`、`pick_reply`、`snprintf`、`strlen`、`strncat`

**被调用：** `src/ai.c :: ai_mode`、`src/gui.c :: answer_q`、`src/server.c :: answer_q`、`src/solver.c :: handle`、`src/test_answer.c :: answer_q`、`tools/gui_part.c :: answer_q`、`tools/server_part.c :: answer_q`

### `u8_next()`

**调用：** `u8_prev`

**被调用：** `src/ai.c :: collect_numbers`、`src/ai.c :: parse_cn`、`src/gui.c :: collect_numbers`、`src/gui.c :: parse_cn`、`src/server.c :: collect_numbers`、`src/server.c :: parse_cn`、`src/solver.c :: collect_numbers`、`src/solver.c :: parse_cn`、`src/test_answer.c :: collect_numbers`、`src/test_answer.c :: parse_cn`

### `verify_chain()`

**调用：** `atof`、`eval_expr`、`fabs`、`fmax`、`isnan`、`memcpy`、`memset`、`strchr`、`strlen`、`strrchr`、`strstr`

**被调用：** `src/ai.c :: think_mode`、`src/gui.c :: think_mode`、`src/nanogpt.c :: think_mode`、`src/server.c :: think_mode`、`src/test_answer.c :: think_mode`

### `xrand()`

**调用：** 无（叶子函数）

**被调用：** `src/ai.c :: frand`、`src/ai.c :: gradcheck`、`src/ai.c :: sample_batch`、`src/gui.c :: frand`、`src/gui.c :: gradcheck`、`src/gui.c :: sample_batch`、`src/nanogpt.c :: frand`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: sample_batch`、`src/nanogpt_dbl.c :: frand`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: sample_batch`

### `zero_grads()`

**调用：** `memset`

**被调用：** `src/ai.c :: gradcheck`、`src/ai.c :: train`、`src/gui.c :: gradcheck`、`src/gui.c :: train`、`src/nanogpt.c :: gradcheck`、`src/nanogpt.c :: train`、`src/nanogpt_dbl.c :: gradcheck`、`src/nanogpt_dbl.c :: train`、`src/server.c :: gradcheck`、`src/server.c :: train`、`src/test_answer.c :: gradcheck`、`src/test_answer.c :: train`

---

## `tools/agent_r1.py`

### `_send()`

**调用：** `end_headers`、`len`、`send_header`、`send_response`、`str`、`write`

**被调用：** `deploy/stage/agent_r1.py :: do_GET`、`deploy/stage/agent_r1.py :: do_POST`、`deploy/stage/serve_r1.py :: do_GET`、`deploy/stage/serve_r1.py :: do_POST`、`tools/agent_r1.py :: do_GET`、`tools/agent_r1.py :: do_POST`、`tools/serve_r1.py :: do_GET`、`tools/serve_r1.py :: do_POST`

### `do_GET()`

**调用：** `_send`、`abspath`、`dirname`、`join`、`open`、`read`

**被调用：** 无（入口函数或未被引用）

### `do_POST()`

**调用：** `Lock`、`_send`、`dumps`、`emit`、`encode`、`end_headers`、`flush`、`get`、`handle_task`、`int`、`loads`、`read`、`send_header`、`send_response`、`strip`、`write`

**被调用：** 无（入口函数或未被引用）

### `emit()`

**调用：** `dumps`、`encode`、`flush`、`write`

**被调用：** `deploy/stage/agent_r1.py :: do_POST`、`deploy/stage/agent_r1.py :: handle_task`、`deploy/stage/agent_r1.py :: pick_file`、`deploy/stage/serve_r1.py :: do_POST`、`src/ai.c :: try_rules`、`src/gui.c :: try_rules`、`src/server.c :: try_rules`、`src/solver.c :: try_rules`、`src/test_answer.c :: try_rules`、`tools/agent_r1.py :: do_POST`、`tools/agent_r1.py :: handle_task`、`tools/agent_r1.py :: pick_file`

### `handle_task()`

**调用：** `basename`、`emit`、`encode`、`len`、`llama_chat`、`open`、`pick_file`、`read`、`replace`、`rsplit`、`run_verify`、`safe_path`、`strip`、`strip_fence`、`write`

**被调用：** `deploy/stage/agent_r1.py :: do_POST`、`tools/agent_r1.py :: do_POST`

### `llama_chat()`

**调用：** `Request`、`decode`、`dumps`、`encode`、`get`、`loads`、`read`、`rsplit`、`strip`、`urlopen`

**被调用：** `deploy/stage/agent_r1.py :: handle_task`、`deploy/stage/agent_r1.py :: pick_file`、`tools/agent_r1.py :: handle_task`、`tools/agent_r1.py :: pick_file`

### `log_message()`

**调用：** 无（叶子函数）

**被调用：** 无（入口函数或未被引用）

### `main()`

**调用：** `ArgumentParser`、`ThreadingHTTPServer`、`abspath`、`add_argument`、`makedirs`、`parse_args`、`print`、`serve_forever`

**被调用：** 无（入口函数或未被引用）

### `pick_file()`

**调用：** `emit`、`isfile`、`join`、`listdir`、`llama_chat`、`replace`、`sorted`、`strip`

**被调用：** `deploy/stage/agent_r1.py :: handle_task`、`tools/agent_r1.py :: handle_task`

### `run_verify()`

**调用：** `lower`、`run`、`splitext`

**被调用：** `deploy/stage/agent_r1.py :: handle_task`、`tools/agent_r1.py :: handle_task`

### `safe_path()`

**调用：** `ValueError`、`abspath`、`join`、`lstrip`、`replace`、`startswith`

**被调用：** `deploy/stage/agent_r1.py :: handle_task`、`tools/agent_r1.py :: handle_task`

### `strip_fence()`

**调用：** `any`、`append`、`group`、`join`、`rstrip`、`search`、`splitlines`、`startswith`、`strip`

**被调用：** `deploy/stage/agent_r1.py :: handle_task`、`tools/agent_r1.py :: handle_task`

---

## `tools/build_olympiad_corpus.py`

### `norm()`

**调用：** `replace`、`str`、`strip`

**被调用：** 无（入口函数或未被引用）

---

## `tools/build_olympiad_index.py`

### `unescape()`

**调用：** `replace`、`str`、`sub`

**被调用：** 无（入口函数或未被引用）

---

## `tools/download_model.py`

### `main()`

**调用：** `Request`、`dirname`、`exists`、`get`、`getsize`、`int`、`len`、`makedirs`、`open`、`print`、`read`、`round`、`urlopen`、`write`

**被调用：** 无（入口函数或未被引用）

---

## `tools/drive_gui.c`

### `enum_child()`

**调用：** `GetClassNameW`、`GetWindowTextW`、`printf`、`wcscmp`

**被调用：** 无（入口函数或未被引用）

### `enum_top()`

**调用：** `GetClassNameW`、`GetWindowTextW`、`GetWindowThreadProcessId`、`printf`、`wcscmp`

**被调用：** 无（入口函数或未被引用）

### `main()`

**调用：** `EnumChildWindows`、`EnumWindows`、`MultiByteToWideChar`、`SendMessageW`、`SetConsoleOutputCP`、`Sleep`、`WideCharToMultiByte`、`atoi`、`fwrite`、`malloc`、`printf`

**被调用：** 无（入口函数或未被引用）

---

## `tools/extract_books.py`

### `clean()`

**调用：** `strip`、`sub`

**被调用：** `tools/extract_books.py :: from_ipynb`、`tools/extract_books.py :: from_pdf`、`tools/extract_books.py :: main`

### `from_ipynb()`

**调用：** `append`、`clean`、`get`、`isinstance`、`join`、`load`、`open`、`str`、`strip`

**被调用：** `tools/extract_books.py :: main`

### `from_pdf()`

**调用：** `PdfReader`、`append`、`clean`、`extract_text`、`getsize`、`join`、`len`

**被调用：** `tools/extract_books.py :: main`

### `main()`

**调用：** `any`、`basename`、`clean`、`dirname`、`endswith`、`from_ipynb`、`from_pdf`、`get`、`items`、`join`、`len`、`lower`、`makedirs`、`open`、`print`、`read`、`relpath`、`sorted`、`splitext`、`walk`、`write`

**被调用：** 无（入口函数或未被引用）

---

## `tools/fix_olympiad_corpus.py`

### `unescape()`

**调用：** `replace`、`str`、`sub`

**被调用：** 无（入口函数或未被引用）

---

## `tools/fix_stream_nonthinking.py`

### `patch()`

**调用：** `open`、`parse`、`print`、`read`、`replace`、`write`

**被调用：** 无（入口函数或未被引用）

---

## `tools/gen_func_map.py`

### `build_reverse()`

**调用：** `append`、`items`、`set`、`setdefault`、`split`

**被调用：** `tools/gen_func_map.py :: main`

### `main()`

**调用：** `build_reverse`、`discard`、`endswith`、`get`、`join`、`len`、`makedirs`、`open`、`parse_c`、`parse_python`、`print`、`set`、`sorted`、`split`、`sum`、`values`、`walk_sources`、`write`

**被调用：** 无（入口函数或未被引用）

### `parse_c()`

**调用：** `add`、`compile`、`end`、`enumerate`、`finditer`、`group`、`len`、`list`、`open`、`print`、`read`、`set`、`start`、`strip_comments_and_strings`

**被调用：** `tools/gen_func_map.py :: main`

### `parse_python()`

**调用：** `add`、`isinstance`、`open`、`parse`、`print`、`read`、`set`、`walk`

**被调用：** `tools/gen_func_map.py :: main`

### `strip_comments_and_strings()`

**调用：** `sub`

**被调用：** `tools/gen_func_map.py :: parse_c`

### `walk_sources()`

**调用：** `join`、`lower`、`relpath`、`replace`、`splitext`、`startswith`、`walk`

**被调用：** `tools/gen_func_map.py :: main`

---

## `tools/gui_part.c`

### `answer_q()`

**调用：** `MultiByteToWideChar`、`WideCharToMultiByte`、`chat_reply`、`eval_expr`、`is_arith_s`、`isnan`、`malloc`、`snprintf`、`solve_linear`、`strchr`、`try_rules`、`utf8_to_w`、`w_to_utf8`

**被调用：** `src/gui.c :: do_send`、`src/server.c :: load_sessions`、`src/test_answer.c :: main`、`tools/gui_part.c :: do_send`、`tools/server_part.c :: load_sessions`、`tools/test_main.c :: main`

### `append_history()`

**调用：** `GetWindowTextLengthW`、`SendMessageW`、`wcscat`

**被调用：** `src/gui.c :: do_send`、`src/gui.c :: wndproc`、`tools/gui_part.c :: do_send`、`tools/gui_part.c :: wndproc`

### `do_send()`

**调用：** `GetWindowTextW`、`SetWindowTextW`、`answer_q`、`append_history`、`fclose`、`fopen`、`fprintf`、`free`、`utf8_to_w`、`w_to_utf8`

**被调用：** `src/gui.c :: wndproc`、`tools/gui_part.c :: wndproc`

### `inp_proc()`

**调用：** `CallWindowProc`、`GetParent`、`SendMessage`

**被调用：** 无（入口函数或未被引用）

### `is_arith_s()`

**调用：** `isdigit`、`strchr`

**被调用：** `src/ai.c :: ai_mode`、`src/gui.c :: answer_q`、`src/server.c :: answer_q`、`src/test_answer.c :: answer_q`、`tools/gui_part.c :: answer_q`、`tools/server_part.c :: answer_q`

### `main()`

**调用：** `CreateWindowW`、`DispatchMessageW`、`GetMessageW`、`GetModuleHandleW`、`LoadCursor`、`MessageBoxA`、`RegisterClassW`、`ShowWindow`、`TranslateMessage`、`alloc_activations`、`init_params`、`load_corpus`、`load_weights`、`memset`

**被调用：** 无（入口函数或未被引用）

### `rep()`

**调用：** `memcpy`、`strlen`

**被调用：** `src/gui.c :: repf`、`src/server.c :: repf`、`src/test_answer.c :: repf`、`tools/gui_part.c :: repf`、`tools/server_part.c :: repf`

### `repf()`

**调用：** `rep`、`va_end`、`va_start`、`vsnprintf`

**被调用：** `src/gui.c :: chat_reply`、`src/gui.c :: emit`、`src/server.c :: chat_reply`、`src/server.c :: emit`、`src/test_answer.c :: chat_reply`、`src/test_answer.c :: emit`

### `sess_append()`

**调用：** `memcpy`、`strlen`

**被调用：** `src/test_answer.c :: answer_q`

### `wndproc()`

**调用：** `CreateFontW`、`CreateWindowW`、`DefWindowProcW`、`LOWORD`、`PostQuitMessage`、`SendMessageW`、`SetFocus`、`SetWindowLongPtrW`、`append_history`、`do_send`

**被调用：** 无（入口函数或未被引用）

---

## `tools/local_proxy.py`

### `_proxy()`

**调用：** `HTTPConnection`、`close`、`end_headers`、`flush`、`get`、`getheaders`、`getresponse`、`int`、`items`、`lower`、`read`、`request`、`send_header`、`send_response`、`write`

**被调用：** `tools/local_proxy.py :: do_GET`、`tools/local_proxy.py :: do_POST`

### `do_GET()`

**调用：** `_proxy`

**被调用：** 无（入口函数或未被引用）

### `do_POST()`

**调用：** `_proxy`

**被调用：** 无（入口函数或未被引用）

### `log_message()`

**调用：** 无（叶子函数）

**被调用：** 无（入口函数或未被引用）

### `main()`

**调用：** `ArgumentParser`、`ThreadingHTTPServer`、`add_argument`、`parse_args`、`print`、`serve_forever`

**被调用：** 无（入口函数或未被引用）

---

## `tools/make_gui.py`

### `cut()`

**调用：** `chr`、`count`、`index`、`print`

**被调用：** 无（入口函数或未被引用）

### `to_rep()`

**调用：** `replace`

**被调用：** 无（入口函数或未被引用）

---

## `tools/make_server.py`

### `cut()`

**调用：** `chr`、`count`、`index`、`print`

**被调用：** 无（入口函数或未被引用）

### `to_rep()`

**调用：** `replace`

**被调用：** 无（入口函数或未被引用）

---

## `tools/make_test.py`

### `cut()`

**调用：** `index`、`print`

**被调用：** 无（入口函数或未被引用）

### `to_rep()`

**调用：** `replace`

**被调用：** 无（入口函数或未被引用）

---

## `tools/merge_ai.py`

### `cut()`

**调用：** `chr`、`count`、`index`、`print`

**被调用：** 无（入口函数或未被引用）

---

## `tools/patch_verbose.py`

### `patch()`

**调用：** `open`、`parse`、`print`、`read`、`replace`、`write`

**被调用：** 无（入口函数或未被引用）

---

## `tools/serve_r1.py`

### `_grams()`

**调用：** `isspace`、`join`、`len`、`range`

**被调用：** `deploy/package/worker.py :: build_index`、`deploy/package/worker.py :: retrieve`、`deploy/stage/serve_r1.py :: build_index`、`deploy/stage/serve_r1.py :: retrieve`、`deploy/stage/worker.py :: build_index`、`deploy/stage/worker.py :: retrieve`、`deploy/worker.py :: build_index`、`deploy/worker.py :: retrieve`、`tools/serve_r1.py :: build_index`、`tools/serve_r1.py :: load_olympiad`、`tools/serve_r1.py :: retrieve`、`tools/serve_r1.py :: retrieve_olympiad`

### `_send()`

**调用：** `end_headers`、`len`、`send_header`、`send_response`、`str`、`write`

**被调用：** `deploy/stage/agent_r1.py :: do_GET`、`deploy/stage/agent_r1.py :: do_POST`、`deploy/stage/serve_r1.py :: do_GET`、`deploy/stage/serve_r1.py :: do_POST`、`tools/agent_r1.py :: do_GET`、`tools/agent_r1.py :: do_POST`、`tools/serve_r1.py :: do_GET`、`tools/serve_r1.py :: do_POST`

### `build_index()`

**调用：** `_grams`、`append`、`exists`、`len`、`max`、`open`、`print`、`range`、`read`、`strip`、`time`

**被调用：** `deploy/package/worker.py :: main`、`deploy/stage/serve_r1.py :: main`、`deploy/stage/worker.py :: main`、`deploy/worker.py :: main`、`src/solver.c :: main`、`tools/serve_r1.py :: main`

### `do_GET()`

**调用：** `_send`、`dumps`、`encode`、`get`、`items`、`join`、`open`、`parse_qs`、`read`、`sort`、`urlparse`

**被调用：** 无（入口函数或未被引用）

### `do_POST()`

**调用：** `_send`、`append`、`dumps`、`emit`、`encode`、`end_headers`、`enumerate`、`flush`、`get`、`int`、`join`、`len`、`list`、`loads`、`max`、`new_sid`、`read`、`retrieve`、`retrieve_olympiad`、`save_session`、`send_header`、`send_response`、`stream_llama`、`strip`、`strip_refs`、`urlparse`、`write`

**被调用：** 无（入口函数或未被引用）

### `emit()`

**调用：** `dumps`、`encode`、`flush`、`write`

**被调用：** `deploy/stage/agent_r1.py :: do_POST`、`deploy/stage/agent_r1.py :: handle_task`、`deploy/stage/agent_r1.py :: pick_file`、`deploy/stage/serve_r1.py :: do_POST`、`src/ai.c :: try_rules`、`src/gui.c :: try_rules`、`src/server.c :: try_rules`、`src/solver.c :: try_rules`、`src/test_answer.c :: try_rules`、`tools/agent_r1.py :: do_POST`、`tools/agent_r1.py :: handle_task`、`tools/agent_r1.py :: pick_file`

### `load_olympiad()`

**调用：** `_grams`、`exists`、`get`、`len`、`load`、`open`、`print`

**被调用：** `tools/serve_r1.py :: main`

### `load_sessions()`

**调用：** `endswith`、`join`、`listdir`、`load`、`makedirs`、`open`

**被调用：** `deploy/stage/serve_r1.py :: main`、`src/server.c :: main`、`tools/serve_r1.py :: main`、`tools/server_part.c :: main`

### `log_message()`

**调用：** 无（叶子函数）

**被调用：** 无（入口函数或未被引用）

### `main()`

**调用：** `ArgumentParser`、`ThreadingHTTPServer`、`add_argument`、`build_index`、`load_olympiad`、`load_sessions`、`parse_args`、`print`、`serve_forever`

**被调用：** 无（入口函数或未被引用）

### `new_sid()`

**调用：** `int`、`time`

**被调用：** `deploy/stage/serve_r1.py :: do_POST`、`tools/serve_r1.py :: do_POST`

### `retrieve()`

**调用：** `_grams`、`append`、`enumerate`、`len`、`sort`

**被调用：** `deploy/package/worker.py :: answer`、`deploy/stage/serve_r1.py :: do_POST`、`deploy/stage/worker.py :: answer`、`deploy/worker.py :: answer`、`tools/serve_r1.py :: do_POST`

### `retrieve_olympiad()`

**调用：** `_grams`、`append`、`get`、`len`、`set`、`sort`

**被调用：** `tools/serve_r1.py :: do_POST`

### `save_session()`

**调用：** `dump`、`join`、`makedirs`、`open`

**被调用：** `deploy/stage/serve_r1.py :: do_POST`、`tools/serve_r1.py :: do_POST`

### `stream_llama()`

**调用：** `Request`、`decode`、`dumps`、`encode`、`get`、`int`、`loads`、`lstrip`、`print`、`split`、`startswith`、`strip`、`time`、`urlopen`

**被调用：** `deploy/stage/serve_r1.py :: do_POST`、`tools/serve_r1.py :: do_POST`

### `strip_refs()`

**调用：** `strip`、`sub`

**被调用：** `deploy/stage/serve_r1.py :: do_POST`、`tools/serve_r1.py :: do_POST`

### `strip_thinking()`

**调用：** `rsplit`、`strip`

**被调用：** 无（入口函数或未被引用）

---

## `tools/server_part.c`

### `answer_q()`

**调用：** `chat_reply`、`eval_expr`、`is_arith_s`、`isnan`、`snprintf`、`solve_linear`、`strchr`、`try_rules`

**被调用：** `src/gui.c :: do_send`、`src/server.c :: load_sessions`、`src/test_answer.c :: main`、`tools/gui_part.c :: do_send`、`tools/server_part.c :: load_sessions`、`tools/test_main.c :: main`

### `is_arith_s()`

**调用：** `isdigit`、`strchr`

**被调用：** `src/ai.c :: ai_mode`、`src/gui.c :: answer_q`、`src/server.c :: answer_q`、`src/test_answer.c :: answer_q`、`tools/gui_part.c :: answer_q`、`tools/server_part.c :: answer_q`

### `load_sessions()`

**调用：** `ShellExecuteA`、`_mkdir`、`answer_q`、`closesocket`、`fclose`、`fflush`、`find_session`、`fopen`、`fprintf`、`fread`、`free`、`http_send`、`json_escape`、`json_get`、`malloc`、`new_session`、`sess_append_log`、`snprintf`、`strcpy`、`strlen`、`strncmp`、`strstr`

**被调用：** `deploy/stage/serve_r1.py :: main`、`src/server.c :: main`、`tools/serve_r1.py :: main`、`tools/server_part.c :: main`

### `main()`

**调用：** `SetConsoleOutputCP`、`alloc_activations`、`atoi`、`fprintf`、`init_params`、`load_corpus`、`load_sessions`、`load_weights`、`serve`

**被调用：** 无（入口函数或未被引用）

### `rep()`

**调用：** `memcpy`、`strlen`

**被调用：** `src/gui.c :: repf`、`src/server.c :: repf`、`src/test_answer.c :: repf`、`tools/gui_part.c :: repf`、`tools/server_part.c :: repf`

### `repf()`

**调用：** `rep`、`va_end`、`va_start`、`vsnprintf`

**被调用：** `src/gui.c :: chat_reply`、`src/gui.c :: emit`、`src/server.c :: chat_reply`、`src/server.c :: emit`、`src/test_answer.c :: chat_reply`、`src/test_answer.c :: emit`

### `sess_append_log()`

**调用：** `fclose`、`find_session`、`fopen`、`fwrite`、`malloc`、`memcpy`、`new_session`、`realloc`、`snprintf`、`strcmp`、`strlen`

**被调用：** `src/server.c :: load_sessions`、`tools/server_part.c :: load_sessions`

---

## `tools/test_main.c`

### `main()`

**调用：** `SetConsoleOutputCP`、`alloc_activations`、`answer_q`、`fflush`、`init_params`、`load_corpus`、`load_weights`、`printf`

**被调用：** 无（入口函数或未被引用）

---

## `tools/train_lora.py`

### `main()`

**调用：** `AdamW`、`ArgumentParser`、`LoraConfig`、`abspath`、`add_argument`、`append`、`backward`、`clip_grad_norm_`、`from_pretrained`、`get_num_threads`、`get_peft_model`、`gradient_checkpointing_enable`、`item`、`len`、`makedirs`、`model`、`open`、`parameters`、`parse_args`、`print`、`print_trainable_parameters`、`randrange`、`read`、`save_pretrained`、`set_num_threads`、`step`、`sum`、`time`、`tok`、`train`、`unsqueeze`、`zero_grad`

**被调用：** 无（入口函数或未被引用）

