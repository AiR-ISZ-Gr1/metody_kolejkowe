import io
import asyncio
import numpy as np
import streamlit as st  # Import streamlit
import matplotlib.pyplot as plt  # Import matplotlib
from visual_functions import process_queue_data, plot_buffer_levels, plot_processing_times

from simulation import simulate, route_random, route_shortest_queue, create_requests_generator_poisson, logger, log_format

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
        logs_title = st.title("Status symulacji")
        log_placeholder = st.empty()
        log_stream = io.StringIO()

        def custom_log_handler(message):
            log_stream.write(message)  # Write log message to the string buffer
            
            log_lines = log_stream.getvalue().splitlines()[-15:]  # Get last 10 lines
            while len(log_lines) < 15:
                log_lines.append(" ")
            log_content = "\n\n".join(log_lines)  # Join the lines to display
            
            # Custom style for the log area (changing the background)
            log_placeholder.markdown(f"""
                <div style="background-color: #f0f0f0; padding: 10px; border-radius: 10px;">
                    <pre style="white-space: pre-wrap; word-wrap: break-word;">{log_content}</pre>
                </div>
            """, unsafe_allow_html=True)
            
            # log_placeholder.text_area("Logger output:", log_stream.getvalue(), height=200)
        logger.add(custom_log_handler, format=log_format, level="INFO")
        

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(simulate(
            num_servers=num_servers,
            server_buffer_size=server_buffer_size,
            server_mu=server_mu,
            routing_fn=routing_fn,
            request_generator=request_generator,
            simulation_time=simulation_time,
            logging=True
        ))
        
        logs_title.empty()
        log_placeholder.empty()


        # Wyświetlamy wyniki
        st.subheader("Wyniki symulacji:")
        st.write(f"Przetworzone zgłoszenia: {results['total_processed']}")
        st.write(f"Odrzucone zgłoszenia: {results['total_rejected']}")
        
        file_path = results["path_to_logs"]
        data_df, result, rejects = process_queue_data(file_path)
        # data_df[data_df['source'] == 'WS2']
        max_buffer = server_buffer_size + 1  # Set the maximum buffer level as needed
        plot_buffer_levels(data_df, rejects, max_buffer)
        plot_processing_times(result)
        
        
        


if __name__ == '__main__':
    main()
