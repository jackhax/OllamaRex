#!/usr/bin/env python3

import os
import json
import graphlib
import requests
import backoff
import argparse

# For generating html web page for summaries
from function_summeries import generate_function_summaries_html

# For syntax highlighting
from pygments import highlight, lexers, formatters

DEBUG = False

def clean_decomp(decomp):
    return decomp.strip('\n') + '\n'

# Misc graph util functions
def transitive_deps(func, callgraph):
    deps = set()
    def dfs(func):
        for callee in callgraph.get(func, []):
            if callee not in deps:
                deps.add(callee)
                dfs(callee)
    dfs(func)
    return deps

def subgraph(callgraph, root):
    subgraph = {}
    subgraph[root] = callgraph.get(root, [])
    for func in transitive_deps(root, callgraph):
        subgraph[func] = callgraph.get(func, [])
    return subgraph

def print_call_tree(root, callgraph, depth=0):
    print('  '*depth + root)
    for callee in callgraph.get(root, []):
        print_call_tree(callee, callgraph, depth+1)

# Custom exception for prompt too long errors so that we can use the
# same function for simulation and actual summarization
class PromptTooLongError(Exception):
    pass

@backoff.on_exception(backoff.expo, requests.exceptions.RequestException)
def summarize(text, model, max_tokens=256):
    if DEBUG:
        print("PROMPT:")
        print(text)
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": text,
                "stream": False
            }
        )
        response.raise_for_status()
        completion = response.json()['response'].strip()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error while communicating with the custom LLM API: {e}")
    if DEBUG:
        print("SUMMARY:")
        print(completion)
    return completion

def summarize_short_code(decomp, summaries, callees, model):
    prompt = ''
    if len(callees) > 0:
        prompt += 'Given the following summaries:\n'
        for callee in callees:
            if callee in summaries:
                prompt += f'{callee}: {summaries[callee]}\n'
            else:
                prompt += f'{callee}: [Summary not available]\n'
    prompt += "You are a function summarizer. You summarize a given sentence by defining it's logic and its operations  in one word.Describe what this function does in a single sentence."
    prompt += '```\n' + decomp + '\n```\n'
    one_line_summary = summarize(prompt, model=model)
    return one_line_summary


def summarize_long_code(decomp, summaries, callees, max_lines=100, strategy='long', model='phi3:mini'):
    codelines = decomp.split('\n')
    base_prompt = ''
    if len(callees) > 0:
        base_prompt += 'Given the following summaries:\n'
        for callee in callees:
            base_prompt += f'{callee}: {summaries[callee]}\n'
    chunk_summaries = []
    for i in range(0, len(codelines), max_lines):
        prompt = base_prompt
        if len(chunk_summaries) > 0:
            prompt += 'And the following summaries of the code leading up to this snippet:\n'
            for j, chunk_summary in enumerate(chunk_summaries):
                prompt += f'Part {j + 1}: {chunk_summary}\n'
        if strategy == 'long':
            prompt += 'Describe what this code does in a paragraph:\n'
        elif strategy == 'short':
            prompt += 'Describe what this code does in a single sentence:\n'
        else:
            raise ValueError('Invalid strategy')
        prompt += '```\n' + '\n'.join(codelines[i:i + max_lines]) + '\n```\n'
        chunk_summaries.append(
            summarize(prompt, model=model, max_tokens=(512 if strategy == 'long' else 256))
        )
    # Summarize the whole thing
    prompt = 'Given the following summaries of the code:\n'
    for i, chunk_summary in enumerate(chunk_summaries):
        prompt += f'Part {i + 1}/{len(chunk_summaries)}: {chunk_summary}\n'
    prompt += "You are a function summarizer. You summarize a given sentence by defining it's logic and its operations  in one word.Describe what this function does in a single sentence."
    one_line_summary = summarize(prompt, model=model)
    return one_line_summary

def summarize_all(topo_order, callgraph, decompilations, model, max_lines=100, already_summarized=None):
    if already_summarized is None:
        summaries = {}
    else:
        # Make a copy so we don't modify the original
        summaries = already_summarized.copy()

    for func in topo_order:
        if func in summaries:
            continue
        callees = callgraph.get(func, [])
        # Check if func exists in decompilations
        if func not in decompilations:
            print(f"Function '{func}' not found in decompilations. Skipping.")
            continue
        
        decomp = clean_decomp(decompilations[func])
        # First try to summarize the whole function
        summary = None
        try:
            summary = summarize_short_code(decomp, summaries, callees, model)
        except PromptTooLongError:
            pass
        # If that fails, try to summarize the function in chunks of max_lines lines,
        # decreasing max_lines until we find a chunk size that works or num_lines gets
        # too small. We try to summarize in paragraphs first, then sentences.
        num_lines = max_lines
        while summary is None:
            try:
                if DEBUG: print(f"Trying to summarize {func} in chunks of {num_lines} lines with paragraphs...")
                summary = summarize_long_code(decomp, summaries, callees, max_lines=num_lines, strategy='long', model=model)
            except PromptTooLongError:
                num_lines -= 10
                if num_lines < 10:
                    break
        num_lines = max_lines
        while summary is None:
            try:
                if DEBUG: print(f"Trying to summarize {func} in chunks of {num_lines} lines with sentences...")
                summary = summarize_long_code(decomp, summaries, callees, max_lines=num_lines, strategy='short', model=model)
            except PromptTooLongError:
                num_lines -= 10
                if num_lines < 10:
                    break
        if summary is None:
            break
        summaries[func] = summary
        yield { func: summary }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--function', required=False, default=None, help='Summarize only this function (and dependencies)')
    parser.add_argument('-d', '--decompilations', required=False, default='decompilations.json')
    parser.add_argument('-g', '--call-graph', required=False, default='call_graph.json')
    parser.add_argument('-o', '--output', required=False, help='Output file (default: progdir/summaries.jsonl)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('-l', '--max-lines', type=int, default=100, help='Maximum number of lines to summarize at a time')
    parser.add_argument('-m', '--model', required=True, help='Model name to use for summarization')
    parser.add_argument('progdir')

    args = parser.parse_args()
    progdir = args.progdir
    callgraph = json.load(open(os.path.join(progdir, args.call_graph)))
    decompilations = json.load(open(os.path.join(progdir, args.decompilations)))
    global DEBUG
    DEBUG = args.verbose
    if args.function is not None:
        callgraph = subgraph(callgraph, args.function)
        if args.output is None:
            args.output = f'{args.progdir}/summaries_{args.function}_{args.model}.jsonl'
    else:
        if args.output is None:
            args.output = f'{args.progdir}/summaries_{args.model}.jsonl'

    # TODO: handle non-trivial cycles
    topo_order = list(graphlib.TopologicalSorter(callgraph).static_order())

    # Set up highlighting for C
    formatter = formatters.Terminal256Formatter(style='monokai')
    lexer = lexers.get_lexer_by_name('c')
    def debug_summary(func, code, summary):
        print(f"Attempted to summarize {func}:")
        print(highlight(code, lexer, formatter))
        print(f"Callees: {callgraph.get(func, [])}")
        print("Summary:")
        print(summary)
        print()

    from tqdm import tqdm
    tqdm_class = tqdm

    # Create the summaries by summarizing leaf functions first, then
    # working our way up the call graph; for non-leaf functions, we
    # use the summaries of the callees in the prompt
    summaries = {}
    if os.path.exists(args.output):
        with open(args.output, 'r') as f:
            summaries = { list(json.loads(line).keys())[0]: list(json.loads(line).values())[0] for line in f }
    with open(args.output, 'a') as f:
        with tqdm_class(summarize_all(topo_order, callgraph, decompilations, args.model, max_lines=args.max_lines, already_summarized=summaries), total=len(topo_order)) as pbar:
            for summary in pbar:
                f.write(json.dumps(summary) + '\n')
                f.flush()
                if args.verbose:
                    func = list(summary.keys())[0]
                    debug_summary(func, decompilations[func], summary[func])
    
    try:
        generate_function_summaries_html(args.output, os.path.join(progdir, args.decompilations), args.progdir)
    except Exception as e:
        print('Failed to generate HTML for summaries',e)

if __name__ == '__main__':
    main()
