Change log destination to .wflog.csv and have the worker save the log, csv, or dot
Change the init method to a load function
Visualise workers (combined also) working and have ability to stop and start workflow
Have master with stack of active workers and master log
Output list of unique commands
Worker ---list --status --start-from
Group workers (business, competition)
New graph just for worker-worker interaction
Internal kill commandc 
Add worker to pool (business) and start all together (just makes another worker script - as to have businesses run businesses)
Tester worker to see if another worker is active (tester to run for limited time/recursively)
Max number of active workers and memory use
figure out how to merge separate runs into one (should be straight forward with networkx)
function tester wrapper for python with timeit python module with repeats to get an average time for each process (NUS?) and difference between outputs (pytest)
synthesizer (wav in scipy?) for output
