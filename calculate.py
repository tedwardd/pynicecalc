#!/usr/bin/env python3

import click
import configparser
import pprint
import readchar
import requests
import signal
import sys
import time
import json

from pathlib import Path
from nicehash import nicehash

# A cheap way to lookup the values for wtm profitability requests
with open("algo_query_map.json", "r") as f:
    query_map = json.load(f)


def sighandler(signum, frame):
    sys.exit(0)


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


def get_nh_wtm_data(algorithm, coin_filter):
    query = query_map.get(algorithm.lower()).get("url")
    raw_data = (
        requests.get(query).json().get(query_map.get(algorithm.lower()).get("key"))
    )
    coins = list(raw_data.keys())
    rev_sum = 0.0
    if coin_filter == "abcxyzfakecoin123":
        return float(raw_data.get(coins[0]).get("btc_revenue24"))
    for c in coins:
        if coin_filter.upper() in raw_data.get(c).get("tag"):
            rev_sum += float(raw_data.get(c).get("btc_revenue24"))

    return rev_sum


def get_optimal(algo):
    market = "USA"
    if (
        market
        not in requests.get(
            f"https://api2.nicehash.com/main/api/v2/hashpower/orderBook?algorithm={algo}"
        )
        .json()
        .get("stats")
        .keys()
    ):
        market = "EU"
    return (
        requests.get(
            f"https://api2.nicehash.com/main/api/v2/hashpower/order/price?market={market}&algorithm={algo}"
        )
        .json()
        .get("price")
    )


def raise_order(private_api, order_id, new_price, order_limit, order_algo, nh_algos):
    try:
        private_api.set_price_and_limit_hashpower_order(
            order_id, new_price, order_limit, order_algo, nh_algos
        )
    except Exception as e:
        e = str(e)


signal.signal(signal.SIGINT, sighandler)


@click.command()
@click.option(
    "--algorithm", "-a", "algorithm", default=None, multiple=True, required=True
)
@click.option("--coin", "-c", "coin", required=False, default=None, multiple=False)
# The way we're implementing the watch flag feels like a hack
# It is an optional arg that, if not provided, has a value of 0 which is interpreted as "don't loop"
# But if you provide the -w flag it then gets a "default" value of 5 unless you provide your own integer
# after the flag (eg. `-w` would use a value of 5 and `-w 10` would use a value of 10.)
@click.option("--watch", "-w", is_flag=False, flag_value=5, default=0)
@click.option("--config", "config_file", required=False, default="./config.ini")
@click.option("--manage", "-m", is_flag=True, required=False)
def run(algorithm, coin, watch, config_file, manage):

    # Check config path exists
    config = Path(config_file)
    if not config.is_file():
        click.secho(f"{config} does not exist.", bold=True, fg="red")
        sys.exit(1)

    # Parse the config since we know it exists
    config = configparser.ConfigParser()
    config.read(config_file)

    # Create private API interface
    # Also, I hate the nicehash python library. No auth validation on the client instance, smh
    # After we make `private_api` we won't know if the credentials are good until the first time we use it
    # And even then we'll only get a 404 so like... idgaf, just make sure your stuff is right in the config
    private_api = nicehash.private_api(
        config["DEFAULT"]["host"],
        config["DEFAULT"]["organization_id"],
        config["DEFAULT"]["key"],
        config["DEFAULT"]["secret"],
    )

    managed_orders = config.sections()
    rounds_out_of_profit = 0

    seconds_with_work = 0
    seconds_without_work = 0
    # Artificially slow down the rate of raising our order price to be more in-line with the speed at which we can
    # lower it again. This should help smooth out spikes but we might need to make this a user parameter in the future
    without_work_threshold = 600

    # Nicehash only allows us to lower the price once every 10 minutes
    cooldown = 0

    while True:
        out_width_array = []
        # Get the Nicehash data about the algorithms requested
        nh_data = get_nh_data(algorithm)

        # Loop through the returned algo data and process each algo
        for i in nh_data:
            # Get the optimal order price for our algo and cast it to a float
            optimal = float(get_optimal(i.get("algorithm")))
            marketFactor = i.get("displayMarketFactor")

            # Get the current profitability from WTM for the same algo and cast it to a float too
            if coin is None:
                coin = "abcxyzfakecoin123"
            wtm_profitability = float(get_nh_wtm_data(i.get("algorithm"), coin))

            # Print the optimal, profitability
            msg = f"Optimal: {optimal}"
            out_width_array.append(len(msg))
            print(msg)
            msg = f"Profit/{marketFactor}: {wtm_profitability}"
            out_width_array.append(len(msg))
            print(msg)

            # Calculate Expected profit percentage and print that too
            print(optimal)
            print(wtm_profitability)
            perc_profit = round((1 - (optimal / wtm_profitability)) * 100, 2)
            if perc_profit > 0.0:
                color = "green"
                rounds_out_of_profit = 0
            else:
                color = "red"
                rounds_out_of_profit += 1
            msg = f"Theoretical Profit: {perc_profit}%"
            if manage:
                print(str(rounds_out_of_profit * watch) + " seconds out of profit")
            out_width_array.append(len(msg))
            click.secho(msg, fg=color)

        if len(managed_orders) > 0 and manage:
            for order_id in managed_orders:
                if not config.getboolean(order_id, "manage"):
                    continue
                order_details = private_api.request(
                    # Get the order details (requires manual request using private_api)
                    "GET",
                    f"/main/api/v2/hashpower/order/{order_id}",
                    "",
                    "",
                )

                # Further sanity check that the order is active
                if order_details.get("status").get("code") != "ACTIVE":
                    continue

                order_price = float(order_details.get("price"))
                order_algo = order_details.get("algorithm").get("algorithm")
                order_limit = order_details.get("limit")
                msg = f"Current Order Price: {order_price}"
                out_width_array.append(len(msg))
                print(msg)
                exp_perc_profit = round(
                    (1 - (order_price / wtm_profitability)) * 100, 2
                )
                msg = f"Expected Profit: {exp_perc_profit}%"
                out_width_array.append(len(msg))
                print(msg)
                nh_algos = requests.get(
                    "https://api2.nicehash.com/main/api/v2/mining/algorithms"
                ).json()
                buy_info = requests.get(
                    "https://api2.nicehash.com/main/api/v2/public/buy/info"
                ).json()
                for i in buy_info.get("miningAlgorithms"):
                    if i.get("name").upper() == order_algo:
                        step = abs(float(i.get("down_step")))
                        break

                accepted_speed = float(order_details.get("acceptedCurrentSpeed"))

                # Check if order is lower than optimal and lower than profitability
                # Raise the price to be closer to optimal if it's below it
                if (
                    order_price < optimal and accepted_speed == 0.0
                ) and order_price < wtm_profitability:
                    new_price = round(order_price + step, 4)
                    msg = f"Calculated new price: {new_price}"
                    out_width_array.append(len(msg))
                    print(msg)
                    if new_price < wtm_profitability:
                        raise_order(
                            private_api,
                            order_id,
                            new_price,
                            order_limit,
                            order_algo,
                            nh_algos,
                        )

                # If the order price goes above the profitable, try to lower it and start a counter to cancel it (not yet implemented)
                if (
                    order_price > wtm_profitability
                    or order_price > optimal
                    and cooldown <= 0
                ):
                    try:
                        private_api.set_price_and_limit_hashpower_order(
                            order_id,
                            round(order_price - step, 4),
                            order_limit,
                            order_algo,
                            nh_algos,
                        )
                    except Exception as e:
                        cooldown = int(str(e).split(" ")[-1].split('"')[0]) + 1
                        out_width_array.append(len(msg))

                # If we have an order that's in profit but have waited the "without_work_threshold"
                # duration and still have no accepted work, raise the price
                if (
                    order_price < wtm_profitability
                    and exp_perc_profit > perc_profit
                    and seconds_without_work > without_work_threshold
                ):
                    new_price = round(order_price + step, 4)
                    msg = f"Calculated new price: {new_price}"
                    out_width_array.append(len(msg))
                    print(msg)
                    if new_price < wtm_profitability:
                        raise_order(
                            private_api,
                            order_id,
                            new_price,
                            order_limit,
                            order_algo,
                            nh_algos,
                        )

                    seconds_without_work = 0

                # If we have workers but our price is higher than optimal lower it by, at most, the value of $step.
                # If $step were to take us below optimal, lower it to the optimal but never lower.
                if (
                    order_price < wtm_profitability
                    and exp_perc_profit < perc_profit
                    and seconds_with_work > 300
                    and cooldown <= 0
                ):
                    new_price = round(order_price - step, 4)
                    if new_price < optimal:
                        new_price = optimal
                    msg = f"Calculated new price: {new_price}"

                    out_width_array.append(len(msg))
                    print(msg)
                    if new_price < wtm_profitability:
                        raise_order(
                            private_api,
                            order_id,
                            new_price,
                            order_limit,
                            order_algo,
                            nh_algos,
                        )

                    seconds_with_work = 0
                    cooldown = 600

            if accepted_speed == 0.0:
                seconds_without_work += watch
                seconds_with_work = 0
                print(accepted_speed)
                print(
                    f"{seconds_without_work} seconds since we've had accepted shares, will increase order price in {without_work_threshold - seconds_without_work} seconds"
                )
            else:
                seconds_without_work = 0
                seconds_with_work += watch
                print(f"Work accepted for {seconds_with_work} seconds at current price")
                print(f"Cooldown Remaining: {cooldown}s")

        cooldown -= watch

        print("-" * max(out_width_array))
        if watch:
            time.sleep(watch)

        if watch == 0:
            signal.raise_signal(signal.SIGINT)


if __name__ == "__main__":
    run()
