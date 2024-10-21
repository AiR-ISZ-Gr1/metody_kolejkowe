import json
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.cm as cm
import streamlit as st

def process_queue_data(file_path):
    with open(file_path) as file:
        data = json.load(file)
    
    data_df = pd.DataFrame(data)
    
    def convert_to_ms(timestamp):
        m, s, ms = timestamp.split(':')
        total_ms = (int(m) * 60 * 1000) + (int(s) * 1000) + int(ms)
        return round(total_ms, 5)
    
    data_df['ts_in_ms'] = data_df['ts'].apply(convert_to_ms)
    
    queue_count = {}
    
    data_df['currently_in_queue'] = 0

    for index, row in data_df.iterrows():
        source = row['source']
        status = row['status']
        
        if source not in queue_count:
            queue_count[source] = 0
        
        if status == 'queued':
            queue_count[source] += 1
        elif status == 'processed':
            queue_count[source] -= 1
        
        data_df.at[index, 'currently_in_queue'] = queue_count[source]
    
    queued_df = data_df[data_df['status'] == 'queued']
    processed_df = data_df[data_df['status'] == 'processed']
    
    merged_df = pd.merge(queued_df, processed_df, on='request', suffixes=('_queued', '_processed'))
    
    merged_df['processing_time_ms'] = merged_df['ts_in_ms_processed'] - merged_df['ts_in_ms_queued']
    
    result = merged_df[['request', 'ts_queued', 'ts_processed', 'processing_time_ms', 'source_queued']]
    rejects = data_df[data_df['status'] == 'rejected']
    
    return data_df, result, rejects



def plot_buffer_levels(data_df, rejects, max_buffer,plot=True):

    # Get unique sources from the DataFrame
    unique_sources = data_df['source'].unique()
    avg_queues_p = {}
    # Iterate through each source to create the plots
    for source in unique_sources:
        temp_sum = 0
        df_a = data_df[data_df['source'] == source]
        for idx in range(df_a.shape[0]-1):
            temp_sum += (df_a['ts_in_ms'].values[idx+1] - df_a['ts_in_ms'].values[idx]) * df_a['currently_in_queue'].values[idx]
        avg_queue_p = np.round(temp_sum / df_a['ts_in_ms'].values[-1] / max_buffer *100,2)
        avg_queues_p[f'{source}'] =avg_queue_p
        
        source_data = data_df[data_df['source'] == source]
        if plot:
            plt.figure(figsize=(12, 8))
            
            plt.step(source_data['ts_in_ms'], source_data['currently_in_queue'], where='mid', alpha=0)
            plt.fill_between(source_data['ts_in_ms'], source_data['currently_in_queue'], step='mid')

            plt.ylim(0, max_buffer*1.2)
            
            plt.scatter(rejects['ts_in_ms'], np.ones(len(rejects)) * max_buffer, 
                        color='red', s=20, label='Rejected Requests')

            plt.title(f'Buffer Levels for {source}, \nAVG queue fillage - {avg_queue_p}%')
            plt.xlabel('Time')
            plt.ylabel('Currently in Queue')
            plt.legend()
            
            # Set x-axis ticks
            plt.xticks([np.min(source_data['ts_in_ms']), np.max(source_data['ts_in_ms'])])
            
            # Show the plot
            plt.tight_layout()
            st.pyplot(plt)
        else:
            return avg_queues_p

def plot_processing_times(merged_df, plot = True):
    unique_sources = merged_df['source_queued'].unique()
    result = merged_df.copy()
    avg_times = {}
    stds_times = {}
    for source in unique_sources:
        avg_times[f'{source}'] = result[result['source_queued']==source]['processing_time_ms'].mean()
        stds_times[f'{source}'] = result[result['source_queued']==source]['processing_time_ms'].std()
    avg_times['Global'] = result['processing_time_ms'].mean()
    stds_times['Global'] = result[result['source_queued']==source]['processing_time_ms'].std()
   
    if plot:
        num_sources = len(unique_sources)
        cmap = cm.get_cmap('tab20', num_sources)  
        color_mapping = {source: cmap(i) for i, source in enumerate(unique_sources)}

        colors = merged_df['source_queued'].map(color_mapping)
    
        fig = plt.figure(figsize=[12, 8])
        plt.bar(merged_df['request'], merged_df['processing_time_ms'], color=colors)

        plt.xlabel('Request ID')
        plt.ylabel('Processing Time (ms)')
        plt.title('Processing Time per Request')
        

        handles = [plt.Rectangle((0, 0), 1, 1, color=color_mapping[source]) for source in unique_sources]
        plt.legend(handles, unique_sources, title="Source")
        st.pyplot(plt)
    else:
        return avg_times, stds_times