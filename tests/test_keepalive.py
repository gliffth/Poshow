import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
# The keep-alive pinger runs in its own thread against a REAL local server (real `requests`, in a subprocess).
import subprocess, textwrap
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m) or (c or sys.exit(1))
LIB = os.path.join(REPO_ROOT, "api", "_lib")
script = textwrap.dedent(f"""
    import sys, os, time, threading, logging, http.server, socketserver
    sys.path.insert(0, {LIB!r})
    import keepalive as K
    hits = []; mode = {{"status": 200}}
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path); self.send_response(mode["status"]); self.send_header("Content-Length", "2"); self.end_headers(); self.wfile.write(b"ok")
        def log_message(self, *a): pass
    class S(socketserver.ThreadingMixIn, http.server.HTTPServer): daemon_threads = True
    srv = S(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{{srv.server_address[1]}}"

    # URL handling
    assert K.normalise_url(base) == base + "/api/health"
    assert K.normalise_url(base + "/") == base + "/api/health"
    assert K.normalise_url(base + "/api/health") == base + "/api/health"
    assert K.normalise_url("ftp://x/y") is None and K.normalise_url("not a url") is None and K.normalise_url("") is None and K.normalise_url(None) is None
    print("URLS OK")

    # interval clamping
    assert K.KeepAlive(base, 5).interval == 60 and K.KeepAlive(base, 99999).interval == 840 and K.KeepAlive(base, 600).interval == 600
    print("CLAMP OK")

    # logging: only transitions, counted
    recs = []
    class Cap(logging.Handler):
        def emit(self, r): recs.append((r.levelname, r.getMessage()))
    logging.getLogger("keepalive").addHandler(Cap()); logging.getLogger("keepalive").setLevel(logging.INFO)

    ka = K.KeepAlive(base, 0.05, min_interval=0.01, retry_delay=0.05, timeout=2).start()
    t0 = time.time()
    while len(hits) < 4 and time.time() - t0 < 10: time.sleep(0.05)
    assert len(hits) >= 4 and set(hits) == {{"/api/health"}}, hits
    print("PINGS", len(hits) >= 4)
    ups = [r for r in recs if "UP" in r[1]]
    assert len(ups) == 1, recs          # not one log line per ping
    print("LOG ONCE OK")

    # the service starts failing (HTTP 500): the pinger keeps going, logs DOWN once, and recovers
    mode["status"] = 500; n = len(hits)
    t0 = time.time()
    while len(hits) < n + 3 and time.time() - t0 < 10: time.sleep(0.05)
    assert len(hits) >= n + 3 and ka._thread.is_alive()
    downs = [r for r in recs if "DOWN" in r[1]]
    assert len(downs) == 1 and downs[0][0] == "WARNING", recs
    mode["status"] = 200; n = len(hits)
    t0 = time.time()
    while ka.up is not True and time.time() - t0 < 10: time.sleep(0.05)
    assert ka.up is True and len([r for r in recs if "UP" in r[1]]) == 2, recs
    print("RECOVERS OK")

    # the server disappears entirely (connection refused): nothing raises, thread survives
    srv.shutdown(); srv.server_close()
    time.sleep(0.4)
    assert ka._thread.is_alive() and ka.failures >= 1
    print("SURVIVES OUTAGE")
    ka.stop(); assert not ka._thread.is_alive()
    print("STOPS OK", ka._thread.daemon)

    # a raising getter never escapes ping()
    def bad(*a, **k): raise RuntimeError("boom")
    assert K.KeepAlive(base, get=bad).ping() is False
    print("NEVER RAISES")

    # env config
    for k in ("KEEPALIVE_URL", "KEEPALIVE_INTERVAL"): os.environ.pop(k, None)
    assert K.start_from_env() is None
    os.environ["KEEPALIVE_URL"] = "garbage"; assert K.start_from_env() is None
    os.environ["KEEPALIVE_URL"] = "https://example.invalid"; os.environ["KEEPALIVE_INTERVAL"] = "abc"
    e = K.start_from_env(); assert e and e.interval == 600 and e.url == "https://example.invalid/api/health"; e.stop()
    os.environ["KEEPALIVE_INTERVAL"] = "30"; e = K.start_from_env(); assert e.interval == 60; e.stop()
    print("ENV OK")
""")
r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=120)
out = r.stdout
for marker, label in (("URLS OK", "the URL is normalised to /api/health and bad URLs are rejected"),
                      ("CLAMP OK", "the interval is clamped to 60–840 s"),
                      ("PINGS True", "pings repeat against a real server on a background thread"),
                      ("LOG ONCE OK", "it logs the state change once, not on every ping"),
                      ("RECOVERS OK", "HTTP 500s are survived, logged once as DOWN, and recovery is noticed"),
                      ("SURVIVES OUTAGE", "a server that vanishes (connection refused) doesn't kill or crash it"),
                      ("STOPS OK True", "stop() ends the thread; it is a daemon thread (won't block bot shutdown)"),
                      ("NEVER RAISES", "a failing request can never raise out of a ping"),
                      ("ENV OK", "KEEPALIVE_URL / KEEPALIVE_INTERVAL are read, validated and clamped")):
    ok(marker in out, label + ("" if marker in out else f"\n{r.stderr[-600:]}"))
# the bot starts it
src = open(os.path.join(REPO_ROOT, "telegram-bot", "bot.py")).read()
ok("keepalive.start_from_env()" in src and src.index("keepalive.start_from_env()") < src.index("app.run_polling()"), "bot.py starts the pinger before it begins polling")
print("ALL KEEP-ALIVE TESTS PASSED")
