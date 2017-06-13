#!/usr/bin/python

#################################
# Copyright (c) 2017 Justin Sarma, Shutterstock

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

#################################
# This script is designed to calculate appropriate values for the shards.rows parameter passed in to SolrCloud
# for an arbitrary SolrCloud cluster size. It is used to optimize SolrCloud sharded requests to improve performance,
# especially for deeply paginated queries.
#
# Specifically, this script calculates  "shard factor" ratio, defined as shards.rows / (start + rows).
# A Monte Carlo approach is used to simulate the random assignment of documents to shards which takes place during
# solr indexing. In this simulation, we do the following for each page:
# 1. Create shard_count buckets
# 2. Insert P=(current page * rows_per_page) elements into random buckets.
# 3. Determine the max number of elements M over all buckets
# 4. Resulting Shard Factor = M / P, which indicates how many elements we would need
#    to request from each shard to produce a correct set of P elements.
# 5. Clear buckets, and repeat steps 2-4 num_trials times. Determine the minimum shard factor
#    necessary to ensure full accuracy in accurary percent of trials.
# 6. Repeat the process 2-5 for each page in range [1,page_count].
#
# The shard factor will fall as depth increases due to "the law of large numbers".
#
# Example Output:
#
# python estimate_shard_rows.py --trial_count 10000 --page_count 10 --rows_per_page 100 --shard_count 12 --accuracy 99.9
# Depth   Shard factor to use at this depth
# 100     20%
# 200     16%
# 300     15%
# 400     14%
# 500     13%
# 600     12%
# 700     12%
# 800     12%
# 900     11%
# 1000    11%
#
# The above output tells us that if the shard count is 12, and the page size is 100,
# we need to fetch at least 20% of rows to be correct 99.9% of the time on page 1,
# 16% on page 2, 15% on page 3, etc...
#
# Application: 
# 1. Run the above code during cluster setup to generate a table of shard factors.
# 2. Store the output to a table in your service that calls SolrCloud.
# 3. At runtime, for each query, calculate start + rows, an round down to nearest page size in the stored table
#    (eg: start=150, rows=10: 150+10=160 => depth=100
# 4. Lookup query depth in the stored table. (eg: 100 => 20%)
# 5. Append the parameter shards.rows, calculated as follows: shards.rows = shard_factor * (start + rows)
# 6. Sit back and watch performance improve! In our perf tests, average latency dropped by 31% with 12 shards.
#
# See SolrCloud jira ticket here for further context on this issue:
#   https://issues.apache.org/jira/browse/SOLR-5611

# See this blog post for a more complete explanation of how this works, and why it is useful:
#   https://tech.shutterstock.com/2017/05/09/efficiently-handling-deep-pagination-in-a-distributed-search-engine


import numpy as np
import argparse
from random import randint

np.set_printoptions(suppress=True)

# Simulate random distribution of num_tries items into num_buckets buckets
# Return the size of the largest bucket
def sample_probability(num_tries, num_buckets):
    counts = [0] * num_buckets
    for i in range(0,num_tries):
        counts[randint(0,num_buckets-1)] += 1
    return max(counts)

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--trial_count", type=int, dest="trial_count", default=10000,
        help="Number of trials to run per case")
    parser.add_argument("-p", "--page_count", type=int, dest="page_count", default=10,
        help="Number of pages to test")
    parser.add_argument("-r", "--rows_per_page", type=int, dest="rows_per_page", default=100,
        help="Number of rows we want to calculate for.")
    parser.add_argument("-s", "--shard_count", type=int, dest="shard_count", default=4,
        help="Number of shards to calculate for.")
    parser.add_argument("-a", "--accuracy", type=float, dest="accuracy", default=99.0,
        help="Minimum percentage of times we expect all results to be correct.")
    options = parser.parse_args()

    print "Depth\tShard factor to use at this depth"
    depth=options.rows_per_page
    for page in range(0, options.page_count):
        results = []
        for trial in range(0, options.trial_count):
            results.append(sample_probability(depth, options.shard_count))

        # Use the trials to determine how many rows are needed from each bucket to ensure the desired
        # level of accuracy
        num_rows_needed = np.percentile(results, options.accuracy)

        print "%d\t%d%%" % (depth, 100 * num_rows_needed / depth)
        depth += options.rows_per_page

if '__main__' in __name__:
    main()
