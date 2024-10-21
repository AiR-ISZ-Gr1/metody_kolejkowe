import asyncio
import numpy as np
import streamlit as st  # Import streamlit
import matplotlib.pyplot as plt  # Import matplotlib

from simulation import simulate, route_random, route_shortest_queue, create_requests_generator_poisson

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
        # for i, server in enumerate(results["server_queue_lengths"], start=1):
        #     plt.figure(figsize=(12, 6))
        #     plt.plot(server, label=f'Serwer {i}', marker='o')
        #     plt.title("Średnia długość kolejki w czasie")
        #     plt.xlabel("Czas")
        #     plt.ylabel("Długość kolejki")
        #     plt.legend()
        #     st.pyplot(plt)

        # Tworzymy wykres średniej długości kolejki od Ro (lambda_)
        # average_queue_length = np.mean(results["average_queue_lengths"])
        # plt.figure(figsize=(12, 6))
        # plt.bar(['Lambda'], [average_queue_length])
        # plt.title("Średnia długość kolejki w zależności od Ro")
        # plt.ylabel("Średnia długość kolejki")
        # st.pyplot(plt)

if __name__ == '__main__':
    main()
