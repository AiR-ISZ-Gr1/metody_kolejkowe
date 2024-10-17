import random
import numpy as np
import matplotlib.pyplot as plt
from collections import deque

class Moment:
    NEVER = float('inf')

class Server:
    def __init__(self, name, max_queue_size, processing_rate):
        self.name = name
        self.max_queue_size = max_queue_size
        self.processing_rate = processing_rate
        self.queue = deque()
        self.currently_processed_request = None
        self.processing_finish_time = Moment.NEVER

    def queue_length(self):
        return len(self.queue)

    def is_queue_full(self):
        return self.queue_length() >= self.max_queue_size

    def arrive(self, request_id, current_time):
        if self.is_queue_full():
            print(f"[{current_time}] {self.name}: Request {request_id} lost. Queue full")
            return False

        if self.queue_length() == 0 and self.currently_processed_request is None:
            print(f"[{current_time}] {self.name}: Queue empty, processing {request_id} immediately...")
            self.schedule_processing_job(request_id, current_time)
        else:
            self.queue.append(request_id)
            print(f"[{current_time}] {self.name}: Request {request_id} added to queue, queue length: {self.queue_length()}")
        return True

    def schedule_processing_job(self, request_id, current_time):
        print(f"[{current_time}] {self.name}: Started processing {request_id}")
        self.currently_processed_request = request_id
        service_time = self.time_to_next_event()
        self.processing_finish_time = current_time + service_time
        print(f"\tIt will take {service_time} to process this request")

    def finish_processing_job(self, current_time):
        if self.currently_processed_request is None:
            raise Exception("Tried to finish processing but no job was being processed")

        print(f"[{current_time}] {self.name}: Finished processing {self.currently_processed_request}")
        self.currently_processed_request = None

        if self.queue_length() > 0:
            next_request = self.queue.popleft()
            print(f"[{current_time}] {self.name}: Next request {next_request} taken from queue. Queue length: {self.queue_length()}")
            self.schedule_processing_job(next_request, current_time)
        else:
            print(f"[{current_time}] {self.name}: Processing done, no more requests in queue")
            self.processing_finish_time = Moment.NEVER

    def process_request(self, current_time):
        if self.currently_processed_request is not None and current_time >= self.processing_finish_time:
            self.finish_processing_job(current_time)

    def time_to_next_event(self):
        # Generates the service time based on an exponential distribution
        return random.expovariate(self.processing_rate)

class LoadBalancer:
    def __init__(self, arrival_rate, balanced_servers, strategy):
        self.arrival_rate = arrival_rate
        self.servers = balanced_servers
        self.strategy = strategy

    def route_request(self, request_id, current_time):
        server = self.strategy(self.servers)
        return server.arrive(request_id, current_time)

class Simulation:
    def __init__(self, load_balancer, server1, server2, simulation_duration=10):
        self.clock = 0
        self.simulation_duration = simulation_duration
        self.load_balancer = load_balancer
        self.server1 = server1
        self.server2 = server2
        self.queue_lengths = []
        self.dropped_requests = 0

    def step(self):
        request_id = f"Req_{self.clock}"

        # Route a new request based on the strategy
        if not self.load_balancer.route_request(request_id, self.clock):
            self.dropped_requests += 1

        # Process requests on both servers
        self.server1.process_request(self.clock)
        self.server2.process_request(self.clock)

        # Track queue lengths over time
        self.queue_lengths.append((self.clock, self.server1.queue_length(), self.server2.queue_length()))

        # Increment simulation time
        self.clock += 1

    def run(self):
        while self.clock < self.simulation_duration:
            self.step()

    def stats(self):
        avg_queue_length_server1 = np.mean([length[1] for length in self.queue_lengths])
        avg_queue_length_server2 = np.mean([length[2] for length in self.queue_lengths])
        dropped_rate = self.dropped_requests / self.clock
        return avg_queue_length_server1, avg_queue_length_server2, dropped_rate

def random_policy(servers):
    return random.choice(servers)

def shortest_queue_policy(servers):
    return min(servers, key=lambda s: s.queue_length())

# Running the simulation
def simulate():
    initial_lambda = 10
    ro = 2.0
    mi = initial_lambda / ro
    max_queue_size = 10

    server1 = Server("Server A", max_queue_size, mi)
    server2 = Server("Server B", max_queue_size, mi)
    load_balancer = LoadBalancer(initial_lambda, [server1, server2], shortest_queue_policy)

    simulation = Simulation(load_balancer, server1, server2, simulation_duration=10)
    simulation.run()

    avg_queue_A, avg_queue_B, drop_rate = simulation.stats()
    print(f"Avg Queue Length Server A: {avg_queue_A}")
    print(f"Avg Queue Length Server B: {avg_queue_B}")
    print(f"Dropped Request Rate: {drop_rate * 100:.2f}%")

simulate()