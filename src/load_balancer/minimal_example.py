import asyncio
import random
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st

# Parametry systemu (domyślne wartości)
lambda_rate = 10
mu = 1 / 0.5
K = 20
simulation_time = 10

class Server:
    def __init__(self, name, buffer_size):
        self.name = name
        self.queue = asyncio.Queue(maxsize=buffer_size)
        self.processed = 0
        self.rejected = 0
        self.queue_lengths = []  # Przechowywanie długości kolejki w czasie

    async def process_request(self):
        while True:
            request = await self.queue.get()
            service_time = np.random.exponential(1 / mu)
            await asyncio.sleep(service_time)
            self.processed += 1
            self.queue.task_done()
            self.queue_lengths.append(self.queue.qsize())  # Rejestracja długości kolejki

class LoadBalancer:
    def __init__(self, servers):
        self.servers = servers

    async def random_routing(self, arrival_rate):
        while True:
            await asyncio.sleep(np.random.exponential(1 / arrival_rate))
            server = random.choice(self.servers)
            if server.queue.full():
                server.rejected += 1
            else:
                await server.queue.put("request")

    async def shortest_queue_routing(self, arrival_rate):
        while True:
            await asyncio.sleep(np.random.exponential(1 / arrival_rate))
            server = min(self.servers, key=lambda s: s.queue.qsize())
            if server.queue.full():
                server.rejected += 1
            else:
                await server.queue.put("request")

async def simulate(routing_policy):
    server1 = Server("WS1", K)
    server2 = Server("WS2", K)
    servers = [server1, server2]
    load_balancer = LoadBalancer(servers)

    server_tasks = [asyncio.create_task(server.process_request()) for server in servers]

    if routing_policy == "random":
        load_balancer_task = asyncio.create_task(load_balancer.random_routing(lambda_rate))
    elif routing_policy == "shortest_queue":
        load_balancer_task = asyncio.create_task(load_balancer.shortest_queue_routing(lambda_rate))

    await asyncio.sleep(simulation_time)

    load_balancer_task.cancel()
    for task in server_tasks:
        task.cancel()

    total_processed = sum([server.processed for server in servers])
    total_rejected = sum([server.rejected for server in servers])
    avg_queue_length = np.mean([np.mean(server.queue_lengths) for server in servers])

    # Zbieramy dane do wykresów
    queue_lengths = [server.queue_lengths for server in servers]
    return total_processed, total_rejected, avg_queue_length, queue_lengths

def plot_results(results, policy_name):
    total_processed, total_rejected, avg_queue_length, queue_lengths = results

    time_points_ws1 = list(range(len(queue_lengths[0])))
    time_points_ws2 = list(range(len(queue_lengths[1])))

    plt.figure(figsize=(12, 8))

    plt.subplot(2, 1, 1)
    plt.plot(time_points_ws1, queue_lengths[0], label="WS1 Queue Length")
    plt.plot(time_points_ws2, queue_lengths[1], label="WS2 Queue Length")
    plt.title(f"{policy_name} - Queue Lengths")
    plt.xlabel("Time")
    plt.ylabel("Queue Length")
    plt.legend()

    plt.subplot(2, 1, 2)
    plt.bar(["Processed", "Rejected"], [total_processed, total_rejected], color=['green', 'red'])
    plt.title(f"{policy_name} - Processed vs Rejected Requests")

    plt.tight_layout()
    st.pyplot(plt)  # Wyświetlenie wykresu w Streamlit
    plt.close()

# Streamlit interface
st.title("Symulacja Load Balancera")

# Parametry wejściowe od użytkownika
lambda_rate = st.slider("Intensywność napływu zgłoszeń (λ)", min_value=1, max_value=20, value=10)
mu = st.slider("Średni czas obsługi (1/μ)", min_value=0.1, max_value=2.0, value=0.5)
K = st.slider("Rozmiar bufora (K)", min_value=1, max_value=50, value=20)
simulation_time = st.slider("Czas symulacji (sekundy)", min_value=5, max_value=50, value=10)
policy = st.selectbox("Wybierz politykę routingu", ["random", "shortest_queue"])

# Przyciski do uruchomienia symulacji
if st.button("Uruchom symulację"):
    async def run_simulation():
        results = await simulate(policy)
        plot_results(results, f"{policy.capitalize()} Routing")

    # Uruchomienie symulacji asynchronicznej
    asyncio.run(run_simulation())
