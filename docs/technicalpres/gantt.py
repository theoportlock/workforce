import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# Data preparation
tasks = [
    {"Task": "Nextflow Overview and Training", "Start": "2024-04", "End": "2024-06"},
    {"Task": "Pipeline Creation and Testing", "Start": "2024-07", "End": "2024-12"},
    {"Task": "Downstream Analysis Pipeline Design", "Start": "2025-01", "End": "2025-04"},
    {"Task": "Workforce Configuration on multiple systems", "Start": "2025-05", "End": "2025-06"},
    {"Task": "Workforce Package Integration", "Start": "2025-07", "End": "2025-09"},
    {"Task": "Case Study Implementation", "Start": "2025-10", "End": "2026-03"},
    {"Task": "Testing and Debugging", "Start": "2026-04", "End": "2026-07"},
    {"Task": "Continuous Workflows for Data Recording", "Start": "2026-08", "End": "2027-01"},
    {"Task": "Final Review, Documentation, and publication", "Start": "2027-02", "End": "2027-04"}
]

df = pd.DataFrame(tasks)
df['Start'] = pd.to_datetime(df['Start'])
df['End'] = pd.to_datetime(df['End'])

# Convert dates to months from project start
project_start = df['Start'].min()
df['StartWeek'] = ((df['Start'] - project_start) / np.timedelta64(1, 'W')).astype(int) + 1
df['EndWeek'] = ((df['End'] - project_start) / np.timedelta64(1, 'W')).astype(int) + 1

# Plotting the Gantt chart with months from project start on the x-axis
fig, ax = plt.subplots(figsize=(12, 8))

ax.barh(df['Task'], df['EndWeek'] - df['StartWeek'], left=df['StartWeek'], color='skyblue')
ax.set_yticks(np.arange(len(df)))
ax.set_yticklabels(df['Task'])
ax.set_xlabel('Weeks')
ax.set_ylabel('Tasks')

# Set the x-ticks to show months
max_week = df['EndWeek'].max()
ax.set_xticks(np.arange(1, max_week + 1))

plt.title('Research Project Gantt Chart')
plt.tight_layout()
plt.savefig('figures/gantt.pdf')
plt.show()
