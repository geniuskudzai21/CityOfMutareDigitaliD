import argparse
import csv
import os
import pickle
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from database import get_all_employees
from face_utils import encode_face, match_face


def normalize(name):
    return "".join(name.lower().split())


def build_known_set(db_path):
    employees = get_all_employees(db_path)
    encodings = []
    lookup = {}
    for emp in employees:
        if emp["face_encoding"]:
            dec = pickle.loads(emp["face_encoding"])
            encodings.append(dec)
            lookup[len(encodings) - 1] = emp
    return encodings, lookup


def resolve_expected(stem, employees):
    key = normalize(stem)
    for emp in employees:
        if normalize(emp["full_name"]) == key:
            return emp["full_name"]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--test_dir", required=True)
    ap.add_argument("--output", default="results.csv")
    ap.add_argument("--tolerance", type=float, default=0.5)
    args = ap.parse_args()

    known_encodings, lookup = build_known_set(args.db)
    all_employees = get_all_employees(args.db)

    results = []
    conditions = [d for d in os.listdir(args.test_dir)
                  if os.path.isdir(os.path.join(args.test_dir, d))]

    for cond in sorted(conditions):
        cond_dir = os.path.join(args.test_dir, cond)
        for fname in sorted(os.listdir(cond_dir)):
            if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            path = os.path.join(cond_dir, fname)
            stem = os.path.splitext(fname)[0]

            expected = resolve_expected(stem, all_employees)

            start = time.perf_counter()
            enc = encode_face(path)
            if enc is None:
                elapsed = (time.perf_counter() - start) * 1000
                results.append([fname, cond, expected or "None", "None",
                                expected is None, f"{elapsed:.2f}"])
                continue

            idx = match_face(enc, known_encodings, args.tolerance)
            elapsed = (time.perf_counter() - start) * 1000
            actual = lookup[idx]["full_name"] if idx is not None else "None"
            correct = (expected == actual) if expected else (actual == "None")
            results.append([fname, cond, expected or "None", actual,
                            correct, f"{elapsed:.2f}"])

    with open(args.output, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["image_name", "lighting_condition", "expected_match",
                     "actual_match", "correct", "time_taken_ms"])
        w.writerows(results)

    total = len(results)
    correct_count = sum(1 for r in results if r[4] is True)
    false_positives = sum(1 for r in results
                          if r[3] != "None" and r[2] == "None")
    avg_time = sum(float(r[5]) for r in results) / total if total else 0
    accuracy = correct_count / total * 100 if total else 0
    fmr = false_positives / total * 100 if total else 0

    print(f"Total samples:    {total}")
    print(f"Overall accuracy: {accuracy:.2f}%")
    print(f"False match rate: {fmr:.2f}%")
    print(f"Avg recognition:  {avg_time:.2f} ms")
    print(f"Results written to {args.output}")


if __name__ == "__main__":
    main()
