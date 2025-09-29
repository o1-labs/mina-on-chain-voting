# On-Chain Voting Results for [MIPs](https://github.com/MinaProtocol/MIPs)

This article details the calculation of Mina’s on-chain voting results and how to add new MIPs to the
[On-Chain Voting (OCV) Dashboard](https://ocv.minaprotocol.com/) for an upcoming voting period.

Equipped with the tools and knowledge, anyone can independently verify the code, logic, and
results. We always strive for correctness in our code and exhaustively test.

All the code for this project is open source ❤️ and available on [GitHub](https://github.com/o1-labs/mina-on-chain-voting).

Find an issue or a bug? Have a question or suggestion? We’d love to get your [feedback](https://github.com/o1-labs/mina-on-chain-voting/issues)!

# Table of Contents
- [How to add a new MIP](#how-to-add-a-new-mip)
- [Calculation of Mina’s On-Chain Voting Results](#calculation-of-minas-on-chain-voting-results)
  - [Overview](#overview)
  - [Calculating the results](#calculating-the-results-using-mip3mip4-as-examples)
  - [Calculation steps](#calculation-steps)
    - [Obtain staking ledger](#obtain-staking-ledger)
    - [Aggregate voting stake](#aggregate-voting-stake)
    - [Obtain and parse votes](#obtain-and-parse-votes)
    - [Calculate weighted voting results](#calculate-weighted-voting-results)
    - [Adjust Votes and Voting Stake with Non-Delegating Voters](#adjust-votes-and-voting-stake-with-non-delegating-voters)
    - [Vote Verification Scripts](#vote-verification-scripts)
- [Credits](#credits)

## How to add a new MIP
Adding a MIP in the OCV will ensure that the MIP's progress is visible and that the votes are counted and weighed correctly.
To add a new MIP, please follow the following steps:
1. Go to the [MIP list file in the OCV repo](https://github.com/o1-labs/mina-on-chain-voting/blob/main/server/proposals/proposals.json)
2. Click on the pencil icon to edit the file
3. Add a new entry to the list of proposals, following the format of the existing entries
   - the `id` should be the next available integer
   - the `title` should be a descriptive title of the MIP
   - the `key` should be the MIP number (e.g. `MIP5`) - This will be the _memo_ used for voting this MIP
   - the `epoch` should be the epoch number when voting will take place for this MIP
   - the `start_time` and `end_time` should be the timestamps when voting starts and ends for this MIP
   - the `url` should be a link to the MIP's proposal on the [Mina Protocol MIPs repository](https://github.com/MinaProtocol/MIPs/tree/main/MIPS)
   - the network should be `mainnet` or `devnet`
   - the `ledger_hash` must be the ledger hash of the epoch after the voting epoch (e.g. for voting in epoch 53, use the ledger hash of epoch 55). Check how to [obtain the staking ledger](#obtain-staking-ledger) section for more details
4. Once you have added the new entry, scroll down to the bottom of the page and click on the "Propose changes" button
5. In the next page, add a descriptive title and description for your changes, then click on the "Create pull request" button
6. Once the pull request is reviewed and approved, it will be merged into the main branch and the new MIP will be added to the [OCV dashboard](https://ocv.minaprotocol.com/)

## Calculation of Mina’s On-Chain Voting Results
We will describe in detail how to calculate the results of Mina’s on-chain stake-weighted voting!

## Overview
**Note:** This tutorial uses epoch 55 and specific hardcoded values as a concrete example to
demonstrate the voting calculation process. You'll need to adjust these values for your actual use
case.
At a high level, we will

1. Obtain the _next-staking-ledger_ of the next voting epoch
   - The results are calculated using the staking ledger of epoch 55
2. Calculate aggregated voter stake
   - Sum all delegations to each voting public key minus any overriding votes.
   - Voter stake weight is calculated with respect to the total voting stake
3. Obtain transaction data for the voting period, need start and end times
4. Filter the voting (self) transactions, i.e. those with source = receiver
5. Base58 decode the memo field of all votes
6. Calculate yes/no weight
   - Sum yes/no vote stakes
   - Divide by the total voting stake

## Calculating the Results (Using MIP3/MIP4 as Examples)

As mentioned above, this tutorial uses specific historical votes to demonstrate the process. We'll
calculate the results for MIP3 and MIP4 voting:

- _MIP3 Start: 5/20/23 at 6:00 AM UTC (Epoch 53, Slot 2820)_

- _MIP3 End: 5/28/23 at 6:00 AM UTC (Epoch 53, slot 6660)_

- _MIP4 Start: 5/20/23 at 6:00 AM UTC (Epoch 53, Slot 2820)_

- _MIP4 End: 5/28/23 at 6:00 AM UTC (Epoch 53, slot 6660)_

  | Data | Value |
  |------|:------|
  | Epoch | 53 |
  | Keyword | MIP3, MIP4 |
  | Start time | May 20, 2023 06:00 UTC |
  | End time | May 28, 2023 06:00 UTC |

## Calculation steps
### Obtain staking ledger
Since we are calculating the results for MIP3 and MIP4 voting (epoch 53), we need the _next-staking-ledger_ of the next epoch, i.e. the staking ledger of epoch 55.

a. If you are not running a daemon locally, you will first need the ledger hash. Use the query

```
query NextLedgerHash {
  blocks(query: {canonical: true, protocolState: {consensusState: {epoch: 54}}}, limit: 1) {
    protocolState {
      consensusState {
        nextEpochData {
          ledger {
            hash
          }
        }
        epoch
      }
    }
  }
}

response = {
  "data": {
    "blocks": [
      {
        "protocolState": {
          "consensusState": {
            "epoch": 54,
            "nextEpochData": {
              "ledger": {
                "hash": "jw8dXuUqXVgd6NvmpryGmFLnRv1176oozHAro8gMFwj8yuvhBeS"
              }
            }
          }
        }
      }
    ]
  }
}
```
Extract the value corresponding to the deeply nested hash key

`response['data']['blocks'][0]['protocolState']['consensusState']['nextEpochData']['ledger']['hash']
`

b. Now that we have the appropriate ledger hash, we can acquire the corresponding staking ledger, in
fact, the next staking ledger of epoch 54. You can use any of the following sources (extra credit: use them all and check diffs)

- [Mina Explorer’s data archive](https://docs.minaexplorer.com/minaexplorer/data-archive)
- If you’re running a local daemon, you can export the next staking ledger (while we are in epoch 54)
by

`mina ledger export next-staking-ledger > path/to/ledger.json`

and confirm the hash using

`mina ledger hash --ledger-file path/to/ledger.json`

This calculation may take several minutes!

### Aggregate voting stake
a. Calculate each voter's stake from the staking ledger. Aggregate all delegations to each voter (by
default, an account is delegated to itself)
```
agg_stake = {}
delegators = set()

for account in ledger:
    pk = account['pk']
    dg = account['delegate']
    bal = Decimal(account['balance'])

    # pk delegates
    if pk != dg:
        delegators.add(pk)

    try:
        agg_stake[dg] += bal
    except:
        agg_stake[dg] = bal
```

b. Drop delegator votes
```
for d in delegators:
    try:
        del agg_stake[d]
    except:
        pass
```

c. Now agg_stake is a Python dict containing each voter's aggregated stake

### Obtain and parse votes

To obtain all MIP3 and MIP4 votes, we need to get all transactions corresponding to the voting
period (votes are just special transactions after all). It would be nice to be able to prefilter the
transactions more and only fetch what is required, but since memo fields are base58 encoded and any
capitalization of the keyword is valid, prefiltering will be complex and error-prone.

a. Multiple data sources
- Run a local archive node
- Mina Explorer has [GraphQL](https://docs.minaexplorer.com/minaexplorer/graphql-getting-started), and [REST](https://docs.minaexplorer.com/rest-api/ref) APIs

b. Obtain the unique voting transactions
- A vote is a transaction satisfying:
    1. `kind = PAYMENT`
    2. `source = receiver`
    3. Valid _memo_ field (either _mip3_ or _no mip3_)
- Fetch all transactions for the voting period
    1. To avoid our requests getting too big and potentially timing out, we will request the transactions
from each block individually
    2. Block production varies over time; sometimes many blocks are produced in a slot, sometimes no blocks
are produced. A priori, we do not know the exact block heights which constitute the voting period.
We fetch all _canonical_ block heights for the voting period, determined by the _start_ and _end_ times

  ```
  query BlockHeightsInVotingPeriod {
    blocks(query: {canonical: true, dateTime_gte: "2023-05-20T6:00:00Z", dateTime_lte: "2023-05-28T06:00:00Z"}, limit: 7140) {
      blockHeight
    }
  }
  ```

  The max number of slots, hence blocks, in an epoch is _7140_. The response in includes block heights
  _253078_ to _255481_
  ```
  {
    "data": {
      "blocks": [
        {
          "blockHeight": 255481
        },
        ...
        {
          "blockHeight": 253078
        }
      ]
    }
  }
  ```
    3. For each canonical block height in the voting period, query the block’s PAYMENT transactions (votes are payments)

  ```
  query TransactionsInBlockWithHeight($blockHeight: Int!) {
    transactions(query: {blockHeight: $blockHeight, canonical: true, kind: "PAYMENT"}, sortBy: DATETIME_DESC, limit: 1000) {
      blockHeight
      memo
      nonce
      receiver {
        publicKey
      }
      source {
        publicKey
      }
    }
  }
  ```
  where $_blockHeight_ is substituted with each of the voting period’s canonical block heights (
  automation is highly recommended). Again, we include a limit which far exceeds the number of
  transactions in any block so we don’t accidentally get short-changed by a default limit. This
  process will take several minutes if done sequentially. Performance improvements are left as an
  exercise to the reader.

  For example, the response for block _216063_
  ```
  {
    "data": {
      "transactions": [
        {
          "blockHeight": 255481,
          "memo": "E4YM2vTHhWEg66xpj52JErHUBU4pZ1yageL4TVDDpTTSsv8mK6YaH",
          "nonce": 367551,
          "receiver": {
            "publicKey": "B62qjYanmV7y9njVeH5UHkz3GYBm7xKir1rAnoY4KsEYUGLMiU45FSM"
          },
          "source": {
            "publicKey": "B62qre3erTHfzQckNuibViWQGyyKwZseztqrjPZBv6SQF384Rg6ESAy"
          }
        },
        ...
        {
          "blockHeight": 255481,
          "memo": "E4YM2vTHhWEg66xpj52JErHUBU4pZ1yageL4TVDDpTTSsv8mK6YaH",
          "nonce": 105533,
          "receiver": {
            "publicKey": "B62qkiF5CTjeiuV1HSx4SpEytjiCptApsvmjiHHqkb1xpAgVuZTtR14"
          },
          "source": {
            "publicKey": "B62qoXQhp63oNsLSN9Dy7wcF3PzLmdBnnin2rTnNWLbpgF7diABciU6"
          }
        }
      ]
    }
  }
  ```
  Notice the base58 encoded memo field
  4. Concatenate transactions for all canonical blocks in the voting period

3. Filter the votes
   - _memo_ exactly equal to _MIP3_ or _no MIP3_
   - _source_ = _receiver_ (self transaction)
4. The memo field is base58 encoded
5. If there are multiple votes associated with a single public key, only the _latest_ vote is counted;
  _latest_ being defined:
   - For multiple votes from the same account across several blocks, take the vote in the highest block.
   - For multiple votes from the same account in the same block, take the vote with the highest nonce.

### Calculate weighted voting results
  - Sum all aggregated voter stake to get the total voting stake
  - For each delegate, start with their total stake, and subtract the balances of accounts that delegate
  to them with an overriding vote
  - Divide yes/no vote stakes by the total voting stake

### Adjust Votes and Voting Stake with Non-Delegating Voters

Find all votes made by a delegating account, and subtract their account balance from the final voting stake if they disagree with their delegate

```
delegating_stake = {}
delegating_votes = {}
for vote in votes:
    if vote.pk in delegators:
        delegating_stake[vote.pk] = accounts[vote.pk]['balance']
        delegating_votes[vote.pk] = vote.memo
for vote in delegating_votes
    delegate_vote = votes[accounts[pk]['delegate']]
    if against(delegate_vote) and for(vote) and pk not in delegating_votes:
        no_stake -= delegating_stake[vote.pk]
    else if for(delegate_vote) and  against(vote) and pk not in delegating_votes:
        yes_stake -= delegating_stake[vote.pk]
```

Check agreement with the voting results dashboard and/or @trevorbernard’s verification scripts

### Vote Verification Scripts
  - [MIP3](https://gist.github.com/trevorbernard/ec11db89bb9079dd0a01332ef32c0284)
  - [MIP4](https://gist.github.com/trevorbernard/928be21e8e1d9464c3a9b2453d9fd886)

MIP3 and MIP4 Voting Results
- [MIP3 results dashboard](https://ocv.minaprotocol.com/proposal/1/results)
- [MIP4 results dashboard](https://ocv.minaprotocol.com/proposal/2/results)

## Credits

This tutorial is based on the original MIP voting implementation by
the [Granola Team](https://granola.team/about/). Their work on on-chain governance functionality
represents a significant milestone in advancing community participation and decentralization of the
Mina ecosystem.
