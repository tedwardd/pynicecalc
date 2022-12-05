#!/usr/bin/env python3

import requests
import sys
import click
import pprint

from nicehash import nicehash


def get_nh_data(algorithm):
    nh_algos = (
        requests.get("https://api2.nicehash.com/main/api/v2/mining/algorithms")
        .json()
        .get("miningAlgorithms")
    )
    algo_positions = [i.get("algorithm") for i in nh_algos]
    req_data = []
    if len(algorithm) == 0:
        click.secho("Available algorithms:", bold=True, fg="green")
        for i in algo_positions:
            click.secho(f"  - {i}", fg="green")
        sys.exit(0)
    for algo in algorithm:
        algo = algo.upper()
        req_data.append(nh_algos[algo_positions.index(algo)])
    return req_data


def get_nh_wtm_data(algorithm):
    raw_data = (
        requests.get(
            "https://whattomine.com/asic.json?scryptf=true&factor[scrypt_hash_rate]=1000.0&factor[scrypt_power]=0.0&factor[cost]=0.1&factor[cost_currency]=USD&sort=Profit24&volume=0&revenue=24h&factor[exchanges][]=binance&dataset=Main"
        )
        .json()
        .get("coins")
    )
    coins = raw_data.keys()
    for coin in coins:
        if "NICEHASH" in raw_data.get(coin).get("tag"):
            return raw_data.get(coin).get("estimated_rewards")


def get_optimal(algo):
    return (
        requests.get(
            f"https://api2.nicehash.com/main/api/v2/hashpower/order/price?market=USA&algorithm={algo}"
        )
        .json()
        .get("price")
    )


@click.command()
@click.option("--algorithm", "-a", "algorithm", default=None, multiple=True)
def run(algorithm):
    nh_data = get_nh_data(algorithm)
    for i in nh_data:
        optimal = float(get_optimal(i.get("algorithm")))
        wtm_profitability = float(get_nh_wtm_data(i.get("algorithm")))
        print(f"Optimal: {optimal}")
        print(f"Profit/GH: {wtm_profitability}")
        perc_profit = round((1 - (optimal / wtm_profitability)) * 100, 2)
        print(f"Expected Profit: {perc_profit}%")


if __name__ == "__main__":
    run()
