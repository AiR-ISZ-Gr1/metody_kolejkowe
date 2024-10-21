import os
import sys
import fire
import json
import random
import asyncio
import numpy as np
from loguru import logger
from datetime import datetime
from typing import AsyncGenerator, OrderedDict


def log_format(record):
    level = record["level"].name.rjust(4)
    source = record["extra"].get("source", "???")
    time = record["extra"].get("ts") or f"{record['time']:HH:mm:ss.SSS}"
    return f"{time} | {level} | [{source}] {record['message']}\n"


logger.remove()
logger.add(sys.stderr, format=log_format, level="INFO")


type Request = int
type RoutingFn = callable[list[Server], Server]
type RequestGenerator = callable[[], AsyncGenerator[Request, None]]


class Server:
    def __init__(self, name: str, buffer_size: int, mu: float, start_time: datetime) -> None:
        self.name = name
        self.queue = asyncio.Queue(maxsize=buffer_size)
        self.mean_processing_time = mu
        self.start_time = start_time

        self.history = []
        self.processed = 0
        self.rejected = 0

    def ts(self):
        return (datetime.now() - self.start_time + datetime.min).strftime("%M:%S:%f")[:-3]

    async def receive(self, request: Request) -> None:
        if self.queue.full():
            self.rejected += 1

            data = OrderedDict(ts=self.ts(), source=self.name,
                               request=request, status='rejected')
            self.history.append(data)
            logger.info(f"❌ Rejected  request {
                        request:>3} (queue full)", **data)
            return
        data = OrderedDict(ts=self.ts(), source=self.name,
                           request=request, status='queued')
        self.history.append(data)
        logger.debug(f"Queueing request {request}", source=self.name)

        await self.queue.put(request)

    async def simulate_processing_request(self) -> float:
        processing_time = np.random.exponential(self.mean_processing_time)
        await asyncio.sleep(processing_time)
        return processing_time

    async def run(self) -> None:
        while True:
            request = await self.queue.get()
            processing_time = await self.simulate_processing_request()

            self.processed += 1
            self.queue.task_done()

            data = OrderedDict(ts=self.ts(), source=self.name,
                               request=request, status='processed')
            self.history.append(data)
            logger.info((f"✅ Processed request {request:>3} "
                         f"({processing_time:.2f}s)"), **data)


def route_random(servers: list[Server]) -> Server:
    return random.choice(servers)


def route_shortest_queue(servers: list[Server]) -> Server:
    return min(servers, key=lambda s: s.queue.qsize())


def create_requests_generator_poisson(lambda_: float) -> AsyncGenerator[Request, None]:
    cache = []

    async def generator():
        cache_ = iter(cache)
        request = 0
        while True:
            logger.debug(f"Created request {request}", source="GEN")
            yield request
            request += 1

            if not (wait_time := next(cache_, None)):
                wait_time = np.random.exponential(1/lambda_)
                cache.append(wait_time)
            await asyncio.sleep(wait_time)

    return generator


async def run_load_balancer(
    servers: list[Server],
    routing_fn: RoutingFn,
    request_generator: RequestGenerator
) -> None:
    async for request in request_generator():
        server = routing_fn(servers)
        logger.debug(f"Routing request {request} to {
                     server.name}", source="RTR")
        await server.receive(request)


async def simulate(
    num_servers: int,
    server_buffer_size: int,
    server_mu: int,
    routing_fn: RoutingFn,
    request_generator: RequestGenerator,
    simulation_time: float,
) -> None:
    print(f"\nStart symulacji - polityka {routing_fn.__name__}")

    start_time = datetime.now()
    servers = [Server(f"WS{i+1}", server_buffer_size, server_mu, start_time)
               for i in range(num_servers)]

    processes = [
        run_load_balancer(servers, routing_fn, request_generator),
        *[server.run() for server in servers]
    ]
    tasks = [asyncio.create_task(process) for process in processes]

    await asyncio.sleep(simulation_time)

    for task in tasks:
        task.cancel()

    total_processed = sum([server.processed for server in servers])
    total_rejected = sum([server.rejected for server in servers])

    print(f"\nPolityka: {routing_fn.__name__}")
    print(f"Przetworzone zgłoszenia: {total_processed}")
    print(f"Odrzucone zgłoszenia: {total_rejected}")
    print(f"Zgłoszenia w kolejkach: {sum(server.queue.qsize() for server in servers)}")
    logs = [log
            for server in servers
            for log in server.history]
    if os.path.exists(".logs/"):

        num = 0
        while os.path.exists(f'.logs/{routing_fn.__name__}_{num}.json'):
            num += 1
        with open(f".logs/{routing_fn.__name__}_{num}.json", 'w') as f:
            f.write(json.dumps(logs))
            

    return {
        "total_processed": total_processed,
        "total_rejected": total_rejected,
        "logs": logs,
    }

async def simulation_cli(
    num_servers=2,
    server_buffer_size=5,
    server_mu=0.04,
    lambda_=50,
    simulation_time=5,
    routing_fn=None,
):
    """
    Run the load balancer simulation with specified parameters.

    Args:
        num_servers (int): Number of servers.
        server_buffer_size (int): Size of the server buffer.
        server_mu (float): Average time (in seconds) a server takes to process a request.
        lambda_ (float): Average number of incoming requests per second.
        simulation_time (int): Time to run the simulation (in seconds).
        routing_fn (str | tuple | None): Routing function(s) to use. Options: 'random', 'shortest_queue'.
    """

    params = dict(
        num_servers=num_servers,
        server_buffer_size=server_buffer_size,
        server_mu=server_mu,
        request_generator=create_requests_generator_poisson(lambda_=lambda_),
        simulation_time=simulation_time,
    )

    routing_fn = routing_fn or ('random', 'shortest_queue')
    routing_fn = routing_fn if isinstance(routing_fn, tuple) else (routing_fn,)

    for fn_name in routing_fn:
        routing_fn = globals().get(f'route_{fn_name}')
        if not routing_fn:
            raise ValueError(f"Unknown routing function: {fn_name}."
                             " Use 'random' or 'shortest_queue'.")
        await simulate(**params, routing_fn=routing_fn)


if __name__ == '__main__':
    fire.Fire(simulation_cli)
