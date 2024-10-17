import asyncio
import random
import numpy as np

# Parametry systemu
# Intensywność napływu zgłoszeń (średnia liczba zgłoszeń na jednostkę czasu)
lambda_rate = 10
mu = 1/0.5        # Średni czas obsługi 1/0.5 = 2 jednostki czasu, mu = 1/średni_czas_obslugi
K = 5             # Maksymalny rozmiar bufora (kolejki)
simulation_time = 5  # Całkowity czas symulacji w sekundach


class Server:
    def __init__(self, name, buffer_size):
        self.name = name
        # Asynchroniczna kolejka
        self.queue = asyncio.Queue(maxsize=buffer_size)
        self.processed = 0  # Liczba przetworzonych zgłoszeń
        self.rejected = 0  # Liczba odrzuconych zgłoszeń

    async def process_request(self):
        """Obsługa żądania – przetwarzanie"""
        while True:
            request = await self.queue.get()  # Pobierz żądanie z kolejki
            service_time = np.random.exponential(1/mu)
            await asyncio.sleep(service_time)  # Symulacja czasu obsługi
            self.processed += 1
            self.queue.task_done()  # Oznacz zadanie jako ukończone
            print(f"Serwer {self.name} przetworzył zgłoszenie po {
                  service_time:.2f}s, kolejka: {self.queue.qsize()}/{K}")


class LoadBalancer:
    def __init__(self, servers):
        self.servers = servers  # Lista serwerów

    async def random_routing(self, arrival_rate):
        """Polityka losowa – kierowanie żądań do losowego serwera"""
        while True:
            # Czas między nadejściami
            await asyncio.sleep(np.random.exponential(1/arrival_rate))
            server = random.choice(self.servers)
            if server.queue.full():
                server.rejected += 1
                print(f"Zgłoszenie odrzucone przez {
                      server.name}, kolejka pełna")
            else:
                # Dodaj zgłoszenie do kolejki serwera
                await server.queue.put("request")
                print(f"Zgłoszenie skierowane do {
                      server.name}, kolejka: {server.queue.qsize()}/{K}")

    async def shortest_queue_routing(self, arrival_rate):
        """Polityka najkrótszej kolejki – kierowanie żądań do serwera z najkrótszą kolejką"""
        while True:
            # Czas między nadejściami
            await asyncio.sleep(np.random.exponential(1/arrival_rate))
            # Serwer z najkrótszą kolejką
            server = min(self.servers, key=lambda s: s.queue.qsize())
            if server.queue.full():
                server.rejected += 1
                print(f"Zgłoszenie odrzucone przez {
                      server.name}, kolejka pełna")
            else:
                # Dodaj zgłoszenie do kolejki serwera
                await server.queue.put("request")
                print(f"Zgłoszenie skierowane do {
                      server.name}, kolejka: {server.queue.qsize()}/{K}")


async def simulate(routing_policy):
    # Tworzenie serwerów
    server1 = Server("WS1", K)
    server2 = Server("WS2", K)

    servers = [server1, server2]
    load_balancer = LoadBalancer(servers)

    # Uruchamianie procesów serwerów (async)
    server_tasks = [asyncio.create_task(
        server.process_request()) for server in servers]

    # Wybór polityki routingu
    if routing_policy == "random":
        load_balancer_task = asyncio.create_task(
            load_balancer.random_routing(lambda_rate))
    elif routing_policy == "shortest_queue":
        load_balancer_task = asyncio.create_task(
            load_balancer.shortest_queue_routing(lambda_rate))

    # Czas trwania symulacji
    await asyncio.sleep(simulation_time)

    # Zatrzymanie symulacji
    load_balancer_task.cancel()
    for task in server_tasks:
        task.cancel()

    # Wyniki
    total_processed = sum([server.processed for server in servers])
    total_rejected = sum([server.rejected for server in servers])
    avg_queue_length = np.mean([server.queue.qsize() for server in servers])

    print(f"\nPolityka: {routing_policy}")
    print(f"Przetworzone zgłoszenia: {total_processed}")
    print(f"Odrzucone zgłoszenia: {total_rejected}")
    print(f"Średnia długość kolejki: {avg_queue_length}")


# Uruchomienie symulacji
async def main():
    print("Symulacja z polityką losową:")
    await simulate("random")
    print("\nSymulacja z polityką najkrótszej kolejki:")
    await simulate("shortest_queue")

# Uruchomienie głównej funkcji
asyncio.run(main())
