import sys
import json
import random
import asyncio
import os
import numpy as np
from loguru import logger
from typing import AsyncGenerator
from datetime import datetime
from typing import OrderedDict
import streamlit as st  # Import streamlit
import matplotlib.pyplot as plt  # Import matplotlib


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
        self.queue_lengths = []  # Lista do przechowywania długości kolejki

    def ts(self):
        return (datetime.now() - self.start_time + datetime.min).strftime("%H:%M:%S:%f")[:-3]

    async def receive(self, request: Request) -> None:
        if self.queue.full():
            self.rejected += 1

            data = OrderedDict(ts=self.ts(), source=self.name,
                               request=request, status='rejected')
            self.history.append(data)
            logger.info(f"❌ Rejected request {request:>3} (queue full)", **data)
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

            # Zbieranie długości kolejki w każdej iteracji
            self.queue_lengths.append(self.queue.qsize())


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
        logger.debug(f"Routing request {request} to {server.name}", source="RTR")
        await server.receive(request)


async def simulate(
    num_servers: int,
    server_buffer_size: int,
    server_mu: int,
    routing_fn: RoutingFn,
    request_generator: RequestGenerator,
    simulation_time: int,
) -> dict:
    logger.info(f"\nStart symulacji - polityka {routing_fn.__name__}")

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
 
    log_dir = '/data'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logs = [log for server in servers for log in server.history]
    with open(f"{log_dir}/{routing_fn.__name__}.json", 'w') as f:
        f.write(json.dumps(logs))

    average_queue_lengths = [np.mean(server.queue_lengths) for server in servers]

    return {
        "total_processed": total_processed,
        "total_rejected": total_rejected,
        "logs": logs,
        "average_queue_lengths": average_queue_lengths,
        "server_queue_lengths": [server.queue_lengths for server in servers]  # Długości kolejek serwerów
    }


def main():
    st.title("Symulacja Load Balancera")

    # Użytkownik wprowadza parametry
    num_servers = st.number_input("Liczba serwerów", min_value=1, value=2, step=1)
    server_buffer_size = st.number_input("Rozmiar bufora serwera", min_value=1, value=5, step=1)
    server_mu = st.number_input("Średni czas przetwarzania (w sekundach)", min_value=0.01, value=0.04, step=0.01)
    lambda_ = st.number_input("Średnia liczba przychodzących zgłoszeń na sekundę", min_value=0.1, value=50.0, step=0.1)
    simulation_time = st.number_input("Czas symulacji (w sekundach)", min_value=1, value=5, step=1)

    routing_policy = st.selectbox("Wybierz politykę routingu", ["route_random", "route_shortest_queue"])

    if st.button("Uruchom symulację"):
        request_generator = create_requests_generator_poisson(lambda_)
        routing_fn = route_random if routing_policy == "route_random" else route_shortest_queue

        # Uruchamiamy symulację w nowym wątku
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(simulate(
            num_servers=num_servers,
            server_buffer_size=server_buffer_size,
            server_mu=server_mu,
            routing_fn=routing_fn,
            request_generator=request_generator,
            simulation_time=simulation_time
        ))

        # Wyświetlamy wyniki
        st.subheader("Wyniki symulacji:")
        st.write(f"Przetworzone zgłoszenia: {results['total_processed']}")
        st.write(f"Odrzucone zgłoszenia: {results['total_rejected']}")

        # Tworzymy wykresy średniej długości kolejki w czasie
        for i, server in enumerate(results["server_queue_lengths"], start=1):
            plt.figure(figsize=(12, 6))
            plt.plot(server, label=f'Serwer {i}', marker='o')
            plt.title("Średnia długość kolejki w czasie")
            plt.xlabel("Czas")
            plt.ylabel("Długość kolejki")
            plt.legend()
            st.pyplot(plt)

        # Tworzymy wykres średniej długości kolejki od Ro (lambda_)
        average_queue_length = np.mean(results["average_queue_lengths"])
        plt.figure(figsize=(12, 6))
        plt.bar(['Lambda'], [average_queue_length])
        plt.title("Średnia długość kolejki w zależności od Ro")
        plt.ylabel("Średnia długość kolejki")
        st.pyplot(plt)

if __name__ == '__main__':
    main()
