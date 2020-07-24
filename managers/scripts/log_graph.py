#!/usr/bin/env python3
import sys
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd

df = pd.read_csv("../../log.csv", names=["currtime", "starttime", "processname","message"], na_filter=False, skipinitialspace=True)
df["currtime"] = pd.to_datetime(df["currtime"],unit="s")
df["starttime"] = pd.to_datetime(df["starttime"],unit="s")
df.plot.scatter(x="currtime", y="starttime", legend=True)

for index, row in df.iterrows():
    if "start" in row["message"]:
        plt.annotate(row["message"],row[["currtime","starttime"]], xytext=(10,-5), textcoords='offset points', family='sans-serif', fontsize=16, color='darkslategrey')
plt.show()

'''
def graph(log_file):
    # Create graph based on a dataframe
    #plt.savefig("log.pdf")

if __name__ == "__main__":
    graph(sys.argv[1])
'''
