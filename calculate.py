#!/usr/bin/env python3

import requests
import sys
import click

def get_nh_data(algorithm):
    return

@click.command()
@click.option('--algorithm', '-a', 'algorithm', default=None, multiple=True)
def run(algorithm):
    nh_algos = requests.get('https://api2.nicehash.com/main/api/v2/mining/algorithms').json().get('miningAlgorithms')
    algo_positions = [ i.get('algorithm') for i in nh_algos ]
    req_data = []
    if len(algorithm) == 0:
        click.secho("Available algorithms:", bold=True, fg="green")
        for i in algo_positions:
            click.secho(f"  - {i}", fg="green")
        sys.exit(0)
    for algo in algorithm:
        algo = algo.upper()
        req_data.append(nh_algos[algo_positions.index(algo)])
    print(req_data)

if __name__ == '__main__':
    run()