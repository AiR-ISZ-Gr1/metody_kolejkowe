import asyncio
import random
import numpy as np
import matplotlib.pyplot as plt

# Parametry systemu
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
        self.queue_lengths = []  # Dodano: przechowywanie długości kolejki w czasie

    async def process_request(self):
        while True:
            request = await self.queue.get()
            service_time = np.random.exponential(1 / mu)
            await asyncio.sleep(service_time)
            self.processed += 1
            self.queue.task_done()
            self.queue_lengths.append(self.queue.qsize())  # Rejestracja długości kolejki
            print(f"[{self.name}] Przetworzono zgłoszenie, czas obsługi: {service_time:.2f}s, długość kolejki: {self.queue.qsize()}")

class LoadBalancer:
    def __init__(self, servers):
        self.servers = servers

    async def random_routing(self, arrival_rate):
        while True:
            await asyncio.sleep(np.random.exponential(1 / arrival_rate))
            server = random.choice(self.servers)
            if server.queue.full():
                server.rejected += 1
                print(f"[{server.name}] Zgłoszenie odrzucone, kolejka pełna! Odrzucone zgłoszenia: {server.rejected}")
            else:
                await server.queue.put("request")
                print(f"[{server.name}] Zgłoszenie dodane do kolejki, długość kolejki: {server.queue.qsize()}")

    async def shortest_queue_routing(self, arrival_rate):
        while True:
            await asyncio.sleep(np.random.exponential(1 / arrival_rate))
            server = min(self.servers, key=lambda s: s.queue.qsize())
            if server.queue.full():
                server.rejected += 1
                print(f"[{server.name}] Zgłoszenie odrzucone, kolejka pełna! Odrzucone zgłoszenia: {server.rejected}")
            else:
                await server.queue.put("request")
                print(f"[{server.name}] Zgłoszenie dodane do kolejki, długość kolejki: {server.queue.qsize()}")


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

async def main():
    print("Symulacja z polityką losową:")
    random_results = await simulate("random")
    
    print("\nSymulacja z polityką najkrótszej kolejki:")
    shortest_queue_results = await simulate("shortest_queue")

    # Wykresy dla polityki losowej
    plot_results(random_results, "Random Routing")

    # Wykresy dla polityki najkrótszej kolejki
    plot_results(shortest_queue_results, "Shortest Queue Routing")

def plot_results(results, policy_name):
    total_processed, total_rejected, avg_queue_length, queue_lengths = results

    # Dostosowanie liczby punktów czasowych do długości danych o kolejkach
    time_points_ws1 = list(range(len(queue_lengths[0])))
    time_points_ws2 = list(range(len(queue_lengths[1])))

    plt.figure(figsize=(12, 8))

    # Wykresy długości kolejek
    plt.subplot(2, 1, 1)
    plt.plot(time_points_ws1, queue_lengths[0], label="WS1 Queue Length")
    plt.plot(time_points_ws2, queue_lengths[1], label="WS2 Queue Length")
    plt.title(f"{policy_name} - Queue Lengths")
    plt.xlabel("Time")
    plt.ylabel("Queue Length")
    plt.legend()

    # Wykres liczby odrzuconych i przetworzonych zgłoszeń
    plt.subplot(2, 1, 2)
    plt.bar(["Processed", "Rejected"], [total_processed, total_rejected], color=['green', 'red'])
    plt.title(f"{policy_name} - Processed vs Rejected Requests")
    
    plt.tight_layout()
    
    plt.savefig(f"{policy_name}_simulation_results.png")
    plt.close()  # Zamknij wykres, aby uniknąć problemów z pamięcią


# Uruchomienie głównej funkcji
asyncio.run(main())
