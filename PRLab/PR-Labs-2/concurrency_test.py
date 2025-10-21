#!/usr/bin/env python3
"""
Concurrency test harness for Lab 2.
Provides sequential vs. concurrent timing, counter validation, and rate-limit checks.
"""

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed


def fetch_status(url: str) -> tuple[int, float]:
	"""Perform a GET request and return (status, suggested wait)."""
	try:
		with urllib.request.urlopen(url) as response:
			response.read()
			return response.status, 0.0
	except urllib.error.HTTPError as err:
		if err.code == 429:
			retry_header = err.headers.get('Retry-After')
			try:
				retry_after = float(retry_header) if retry_header is not None else 1.0
			except ValueError:
				retry_after = 1.0
			return 429, max(0.5, retry_after)
		raise


def fetch_until_success(url: str) -> tuple[int, int, int]:
	"""Keep requesting until not rate limited; returns (status, attempts, limit_hits)."""
	attempts = 0
	limited_hits = 0
	while True:
		status, retry_after = fetch_status(url)
		attempts += 1
		if status != 429:
			return status, attempts, limited_hits
		limited_hits += 1
		time.sleep(retry_after)


def run_batch(url: str, requests: int, workers: int, retry_on_limit: bool) -> tuple[float, Counter[int], int]:
	"""Send a batch of requests and gather status counts and rate-limit hits."""
	statuses: Counter[int] = Counter()
	limited_hits = 0
	start = time.perf_counter()

	def task():
		if retry_on_limit:
			status, attempts, limited = fetch_until_success(url)
			return status, limited
		status, retry_after = fetch_status(url)
		return status, 1 if status == 429 else 0

	with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
		futures = [pool.submit(task) for _ in range(requests)]
		for future in as_completed(futures):
			status, limited = future.result()
			statuses[status] += 1
			limited_hits += limited

	elapsed = time.perf_counter() - start
	return elapsed, statuses, limited_hits


def maybe_print_json(payload: dict, args: argparse.Namespace) -> None:
	if getattr(args, "json", False):
		print(json.dumps(payload, indent=2))


def benchmark(args: argparse.Namespace) -> None:
	url = f"http://{args.host}:{args.port}{args.path}"
	seq_time, seq_statuses, seq_limited = run_batch(url, args.requests, workers=1, retry_on_limit=False)
	seq_total = sum(seq_statuses.values())
	seq_success = seq_statuses.get(200, 0)
	seq_fail = seq_total - seq_success
	workers = args.workers or args.requests
	conc_time, conc_statuses, conc_limited = run_batch(
		url,
		args.requests,
		workers=workers,
		retry_on_limit=False,
	)
	conc_total = sum(conc_statuses.values())
	conc_success = conc_statuses.get(200, 0)
	conc_fail = conc_total - conc_success
	speedup = seq_time / conc_time if conc_time else float("inf")

	print(f"[benchmark] Target {url}")
	print(f"  Sequential: {seq_time:.2f}s, success={seq_success}, fail={seq_fail}, rate-limit hits={seq_limited}")
	print(f"  Concurrent ({workers} workers): {conc_time:.2f}s, success={conc_success}, fail={conc_fail}, rate-limit hits={conc_limited}")
	print(f"  Speedup (seq/concurrent): {speedup:.2f}x")

	result = {
		"mode": "benchmark",
		"target": url,
		"requests": args.requests,
		"workers": workers,
		"speedup": round(speedup, 2),
		"sequential": {
			"seconds": round(seq_time, 3),
			"status_counts": dict(seq_statuses),
			"rate_limit_hits": seq_limited,
		},
		"concurrent": {
			"seconds": round(conc_time, 3),
			"status_counts": dict(conc_statuses),
			"rate_limit_hits": conc_limited,
		},
	}
	maybe_print_json(result, args)


def run_counter_probe(listing_url: str, target_name: str) -> int | None:
	listing_html = urllib.request.urlopen(listing_url).read().decode()
	pattern = rf"{re.escape(target_name)}[^\\n]*Requests: (\\d+)"
	match = re.search(pattern, listing_html)
	return int(match.group(1)) if match else None


def counter_test(args: argparse.Namespace) -> None:
	target_url = f"http://{args.host}:{args.port}{args.target_path}"
	listing_url = f"http://{args.host}:{args.port}{args.listing_path}"
	worker_count = args.workers or args.requests
	batch_time, status_counts, limited_hits = run_batch(
		target_url,
		args.requests,
		workers=worker_count,
		retry_on_limit=True,
	)
	time.sleep(args.settle)
	count = run_counter_probe(listing_url, args.counter_label)
	success = status_counts.get(200, 0)
	failures = sum(status_counts.values()) - success
	print(f"[counter] Target {target_url}")
	print(f"  Requests fired: {args.requests} (workers={worker_count}) in {batch_time:.2f}s")
	print(f"  Success={success}, fail={failures}, rate-limit retries={limited_hits}")
	if count is None:
		print("  Counter label not found in listing output.")
	else:
		print(f"  Observed count: {count} (expected {args.requests})")
		print("  Status: PASS" if count == args.requests else "  Status: WARN")

	result = {
		"mode": "counter",
		"target": target_url,
		"listing": listing_url,
		"requests": args.requests,
		"workers": worker_count,
		"duration_seconds": round(batch_time, 3),
		"status_counts": dict(status_counts),
		"rate_limit_retries": limited_hits,
		"observed_count": count,
		"expected_count": args.requests,
		"matches": count == args.requests,
	}
	maybe_print_json(result, args)


def rate_limit_test(args: argparse.Namespace) -> None:
	url = f"http://{args.host}:{args.port}{args.path}"
	elapsed, statuses, limited_hits = run_batch(
		url,
		args.requests,
		workers=args.requests,
		retry_on_limit=False,
	)
	total = sum(statuses.values())
	print(f"[rate] Target {url}")
	print(f"  Requests fired: {args.requests} in {elapsed:.2f}s")
	print(f"  Responses: {dict(statuses)} (total {total})")
	print(f"  Rate-limit hits: {limited_hits}")

	result = {
		"mode": "rate-limit",
		"target": url,
		"requests": args.requests,
		"duration_seconds": round(elapsed, 3),
		"status_counts": dict(statuses),
		"rate_limit_hits": limited_hits,
	}
	maybe_print_json(result, args)


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Concurrency benchmarks for the Lab 2 HTTP server.")
	parser.add_argument("mode", choices=["benchmark", "counter", "rate"], help="Test to run.")
	parser.add_argument("--host", default="localhost", help="Server host (default: localhost).")
	parser.add_argument("--port", type=int, default=8080, help="Server port (default: 8080).")
	parser.add_argument("--requests", type=int, default=10, help="Number of requests to send.")
	parser.add_argument("--path", default="/index.html", help="Path to fetch (default: /index.html).")
	parser.add_argument("--workers", type=int, help="Max concurrent workers for benchmark/counter modes.")
	parser.add_argument("--json", action="store_true", help="Also print a JSON summary block.")

	counter_group = parser.add_argument_group("counter")
	counter_group.add_argument("--target-path", default="/index.html", help="Path whose counter should increment.")
	counter_group.add_argument("--listing-path", default="/", help="Directory listing path to inspect.")
	counter_group.add_argument("--counter-label", default="index.html", help="Label to search for in the listing output.")
	counter_group.add_argument("--settle", type=float, default=0.5, help="Seconds to wait before reading counters.")

	return parser.parse_args()


def main() -> None:
	args = parse_args()
	if args.mode == "benchmark":
		benchmark(args)
	elif args.mode == "counter":
		counter_test(args)
	elif args.mode == "rate":
		rate_limit_test(args)


if __name__ == "__main__":
	main()
