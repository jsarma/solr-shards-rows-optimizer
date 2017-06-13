# solr-shards-rows-optimizer

# Summary

This script is designed to calculate appropriate values for the shards.rows parameter passed in to SolrCloud
for an arbitrary SolrCloud cluster size. It is used to optimize SolrCloud sharded requests to improve performance,
especially for deeply paginated queries.

Specifically, this script calculates  "shard factor" ratio, defined as shards.rows / (start + rows).
A Monte Carlo approach is used to simulate the random assignment of documents to shards which takes place during
solr indexing. In this simulation, we do the following for each page:
1. Create shard_count buckets
2. Insert P=(current page * rows_per_page) elements into random buckets.
3. Determine the max number of elements M over all buckets
4. Resulting Shard Factor = M / P, which indicates how many elements we would need
   to request from each shard to produce a correct set of P elements.
5. Clear buckets, and repeat steps 2-4 num_trials times. Determine the minimum shard factor
   necessary to ensure full accuracy in accurary percent of trials.
6. Repeat the process 2-5 for each page in range [1,page_count].

The shard factor will fall as depth increases due to "the law of large numbers".

# Example
```
python estimate_shard_rows.py --trial_count 10000 --page_count 10 --rows_per_page 100 --shard_count 12 --accuracy 99.9
Depth   Shard factor to use at this depth
100     20%
200     16%
300     15%
400     14%
500     13%
600     12%
700     12%
800     12%
900     11%
1000    11%
```
The above output tells us that if the shard count is 12, and the page size is 100,
we need to fetch at least 20% of rows to be correct 99.9% of the time on page 1,
16% on page 2, 15% on page 3, etc...

# Application

1. Run the above code during cluster setup to generate a table of shard factors.
2. Store the output to a table in your service that calls SolrCloud.
3. At runtime, for each query, calculate start + rows, an round down to nearest page size in the stored table
   (eg: start=150, rows=10: 150+10=160 => depth=100
4. Lookup query depth in the stored table. (eg: 100 => 20%)
5. Append the parameter shards.rows, calculated as follows: shards.rows = shard_factor * (start + rows)
6. Sit back and watch performance improve! In our perf tests, average latency dropped by 31% with 12 shards.

# Related

See SolrCloud jira ticket here for further context on this issue:
  https://issues.apache.org/jira/browse/SOLR-5611

See this blog post for a more complete explanation of how this works, and why it is useful:
  https://tech.shutterstock.com/2017/05/09/efficiently-handling-deep-pagination-in-a-distributed-search-engine

