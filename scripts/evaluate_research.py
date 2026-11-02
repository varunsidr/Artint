"""Evaluate the existing RAG pipeline with frozen, local, source-span evidence."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.intelligence import IntelligenceError

from scripts.research_eval.contracts import CORPUS_SCHEMA, EvaluationError, check_disjoint, digest, encoded, load_corpus, write_json
from scripts.research_eval.compare import compare
from scripts.research_eval.review import prepare_review, review_summary
from scripts.research_eval.runner import freeze, run
from scripts.research_eval.development import prepare_development, prepare_gold_review, apply_gold_review
from scripts.research_eval.batch_review import prepare_batch_review


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    schema = commands.add_parser('schema', help='Write the versioned corpus JSON Schema without network access.')
    schema.add_argument('--output', type=Path, required=True)
    validate = commands.add_parser('validate', help='Validate corpus hashes, spans, eligibility and label provenance.')
    validate.add_argument('--corpus', type=Path, required=True)
    splits = commands.add_parser('check-splits', help='Reject exact-text/story leakage across separate corpus files.')
    splits.add_argument('--development', type=Path, required=True)
    splits.add_argument('--heldout', type=Path, required=True)
    frozen = commands.add_parser('freeze', help='Copy a validated corpus into a new frozen directory; no fetches.')
    frozen.add_argument('--corpus', type=Path, required=True)
    frozen.add_argument('--output', type=Path, required=True)
    execute = commands.add_parser('run', help='Run current retrieval or answers with a disposable embedding cache.')
    execute.add_argument('--corpus', type=Path, required=True)
    execute.add_argument('--output', type=Path, required=True)
    execute.add_argument('--engine', choices=['fixture', 'ollama'], default='fixture')
    execute.add_argument('--mode', choices=['retrieval', 'answers'], default='retrieval')
    execute.add_argument('--model', default='qwen3:8b')
    execute.add_argument('--embedding-model', default='qwen3-embedding:0.6b')
    execute.add_argument('--base-url', default='http://127.0.0.1:11434', help='Explicit Ollama endpoint. Source passages are sent here only with --engine ollama.')
    execute.add_argument('--timeout', type=int, default=120)
    execute.add_argument('--repeats', type=int, default=1)
    execute.add_argument('--cache', choices=['cold', 'shared'], default='cold')
    execute.add_argument('--case', action='append', dest='case_ids', help='Select a case ID; repeat to select a declared subset.')
    prepare = commands.add_parser('prepare-review', help='Create pending human labels and a packet with model names omitted.')
    prepare.add_argument('--run', type=Path, required=True)
    prepare.add_argument('--output', type=Path, required=True)
    reviewed = commands.add_parser('review-summary', help='Validate bound human labels; never judge with an LLM.')
    reviewed.add_argument('--run', type=Path, required=True)
    reviewed.add_argument('--review', type=Path, required=True)
    reviewed.add_argument('--second-review', type=Path)
    reviewed.add_argument('--output', type=Path, required=True)
    paired = commands.add_parser('compare', help='Write paired retrieval/latency diagnostics from compatible frozen runs.')
    paired.add_argument('--baseline', type=Path, required=True)
    paired.add_argument('--candidate', type=Path, required=True)
    paired.add_argument('--output', type=Path, required=True)
    development = commands.add_parser('prepare-development', help='Read a saved library without migrations; draft unreviewed questions with explicit local Ollama.')
    development.add_argument('--database', type=Path, required=True)
    development.add_argument('--selection', type=Path, required=True)
    development.add_argument('--output', type=Path, required=True)
    development.add_argument('--model', default='qwen3:8b')
    development.add_argument('--base-url', default='http://127.0.0.1:11434')
    development.add_argument('--timeout', type=int, default=180)
    gold = commands.add_parser('prepare-gold-review', help='Create a local browser/JSON review of proposed development gold labels.')
    gold.add_argument('--corpus', type=Path, required=True)
    gold.add_argument('--output', type=Path, required=True)
    batch = commands.add_parser('prepare-batch-review', help='Create a consolidated offline review of source-bound AI suggestions; no approvals.')
    batch.add_argument('--corpus', type=Path, required=True)
    batch.add_argument('--suggestions', type=Path, required=True)
    batch.add_argument('--output', type=Path, required=True)
    apply = commands.add_parser('apply-gold-review', help='Validate declared human decisions and write a new reviewed corpus, preserving exclusions.')
    apply.add_argument('--corpus', type=Path, required=True)
    apply.add_argument('--review', type=Path, required=True)
    apply.add_argument('--second-review', type=Path)
    apply.add_argument('--output', type=Path, required=True)
    args = vars(parser.parse_args(argv))
    command = args.pop('command')
    try:
        if command == 'schema':
            args['output'].parent.mkdir(parents=True, exist_ok=True)
            write_json(args['output'], CORPUS_SCHEMA)
            result = dict(schema_version=1, output=str(args['output']))
        elif command == 'validate':
            corpus = load_corpus(args['corpus'])
            result = dict(valid=True, kind=corpus['kind'], cases=len(corpus['cases']), sources=len(corpus['sources']), corpus_sha256=digest(encoded(corpus)))
        elif command == 'check-splits':
            check_disjoint(load_corpus(args['development']), load_corpus(args['heldout']))
            result = dict(disjoint=True, limitation='Near-duplicate/syndication grouping still requires human review.')
        elif command == 'freeze':
            result = dict(output=str(freeze(args['corpus'], args['output'])), network=False)
        elif command == 'run':
            corpus_path = args.pop('corpus')
            report = run(corpus_path, **args)
            result = dict(status=report['status'], output=str(args['output']), engine=report['config']['engine'],
                          cases=report['summary']['cases'], failed_runs=report['summary']['failed_runs'], quality_gate='not_established')
            print(json.dumps(result))
            return 0 if report['status'] == 'complete' else 1
        elif command == 'prepare-review':
            result = prepare_review(args['run'], args['output'])
            result = dict(pending_case_runs=len(result['judgments']), output=str(args['output']), human_labels_created=0)
        elif command == 'review-summary':
            result = review_summary(args['run'], args['review'], args['second_review'])
            args['output'].parent.mkdir(parents=True, exist_ok=True)
            write_json(args['output'], result)
        elif command == 'prepare-development':
            result = prepare_development(args['database'], args['selection'], args['output'],
                                         model=args['model'], base_url=args['base_url'], timeout=args['timeout'])
            print(json.dumps({key: result[key] for key in ('status','planned_cases','drafted_cases','proposed_answerable','proposed_unanswerable','human_reviewed_cases')}))
            return 0 if result['status'] == 'complete' else 1
        elif command == 'prepare-gold-review':
            result = prepare_gold_review(args['corpus'], args['output'])
        elif command == 'prepare-batch-review':
            result = prepare_batch_review(args['corpus'], args['suggestions'], args['output'])
        elif command == 'apply-gold-review':
            result = apply_gold_review(args['corpus'], args['review'], args['output'], second_review=args['second_review'])
        else:
            result = compare(args['baseline'], args['candidate'], args['output'])
            result = dict(pairs=len(result['pairs']), output=str(args['output']), quality_gate='not_established')
    except (EvaluationError, IntelligenceError, OSError, ValueError) as exc:
        # Corpus bodies, model response text and credentials are not logged.
        print(f'Evaluation stopped: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 2
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
