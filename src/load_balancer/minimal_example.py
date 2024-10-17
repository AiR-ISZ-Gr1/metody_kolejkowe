from typing import AsyncGenerator
import sys
import asyncio
import random
import numpy as np
from loguru import logger


def log_format(record):
    level = record["level"].name.rjust(4)
    source = record["extra"].get("source", "???")
    return f"{record['time']:YYYY-MM-DD HH:mm:ss} | {level} | [{source}] {record['message']}\n"


logger.remove()
logger.add(
    sys.stderr, format=log_format, level="INFO")


type Request = int
type RoutingFn = callable[list[Server], Server]
type RequestGenerator = callable[[], AsyncGenerator[Request, None]]


class Server:
    def __init__(self, name: str, buffer_size: int, mu: float) -> None:
        self.name = name
        self.queue = asyncio.Queue(maxsize=buffer_size)
        self.mean_processing_time = mu

        self.processed = 0
        self.rejected = 0

    async def receive(self, request: Request) -> None:
        if self.queue.full():
            self.rejected += 1
            logger.info(f"❌ Rejected  request {
                        request:>3} (queue full)", source=self.name)
            return
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

            logger.info((f"✅ Processed request {request:>3} "
                         f"({processing_time:.2f}s)"), source=self.name)


def route_random(servers: list[Server]) -> Server:
    return random.choice(servers)


def route_shortest_queue(servers: list[Server]) -> Server:
    return min(servers, key=lambda s: s.queue.qsize())


def create_requests_generator_poisson(lambda_: float) -> AsyncGenerator[Request, None]:
    async def generator():
        request = 0
        while True:
            logger.debug(f"Created request {request}", source="GEN")
            yield request
            request += 1

            wait_time = np.random.exponential(1/lambda_)
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
    simulation_time: int,
) -> None:
    print(f"\nStart symulacji - polityka {routing_fn.__name__}")

    servers = [Server(f"WS{i+1}", server_buffer_size, server_mu)
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
    avg_queue_length = np.mean(
        [np.mean(server.queue.qsize()) for server in servers])

    print(f"\nPolityka: {routing_fn.__name__}")
    print(f"Przetworzone zgłoszenia: {total_processed}")
    print(f"Odrzucone zgłoszenia: {total_rejected}")
    print(f"Zgłoszenia w kolejkach: {
          sum(server.queue.qsize() for server in servers)}")
    # TODO: to jest do implementacji
    # print(f"Średnia długość kolejki: {avg_queue_length}")


async def main():
    params = dict(
        num_servers=2,
        server_buffer_size=5,
        server_mu=0.7,  # average time in seconds of how long a server takes to process a request
        request_generator=create_requests_generator_poisson(lambda_=4),  # average number of incoming requests per second # noqa
        simulation_time=5,
    )

    await simulate(**params, routing_fn=route_random)
    await simulate(**params, routing_fn=route_shortest_queue)

if __name__ == '__main__':
    asyncio.run(main())
