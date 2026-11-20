# Run guide (for Fil)

The trial lasts 30 days from sign-up, so everything in part 1 happens before you sign up.

## Timing

| When | What | Clock running? |
|---|---|---|
| Today or tomorrow | Part 1: install, rehearse locally, read the SQL | No |
| Saturday 21 or Sunday 22 Nov, when you have 2 clear hours | Part 2 and 3: sign up, connect, run both months | Yes, day 1 |
| The morning after | `python run.py usage` for the credit figure (Snowflake's metering lags up to 3 hours) | Day 2 |
| By Tuesday 24 Nov | Record the 3-minute walkthrough | Day 3 or 4 |
| Wednesday 25 or Thursday 26 Nov | Apply to the Associate Solution Engineer role with the recording and repo link, leaving a buffer before 30 Nov | |
| Around 21 Dec | Trial ends. Everything rebuilds on a fresh account with the same commands if an interviewer wants it live | |

## Part 1: before the trial

1. Copy this folder to your Mac.
2. In a terminal, from the folder:
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-local.txt
   python tests/test_local.py
   ```
   It should end with "All testable criteria pass on the emulator". If it doesn't, paste the output in the thread.
3. Read the SQL in this order and say each part out loud: `sql/02_objects.sql`, `sql/04_copy.sql`, the BIDS section of `sql/05_clean.sql` (the other two sections follow the same pattern), then `sql/06_answers.sql`, then `sql/07_access.sql`. Mark any line you can't explain and ask about it in the thread. The questions an interviewer is most likely to ask are at the bottom.

## Part 2: sign up and connect

1. Sign up at signup.snowflake.com. Choose **Enterprise** edition, **AWS**, region **Europe (London)**. Don't add a card. AI features stay off without one, and this build doesn't use them.
2. Make a key pair in your terminal. The private key never leaves your Mac:
   ```
   mkdir -p ~/.snowflake && cd ~/.snowflake
   openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out marlow_key.p8 -nocrypt
   openssl rsa -in marlow_key.p8 -pubout -out marlow_key.pub
   chmod 600 marlow_key.p8
   grep -v "PUBLIC KEY" marlow_key.pub | tr -d '\n'; echo
   ```
3. In Snowsight, open a new SQL worksheet and run this, pasting the long line the last command printed and using your Snowflake username:
   ```
   ALTER USER YOUR_USERNAME SET RSA_PUBLIC_KEY = 'MIIBIjANBgkq...';
   ```
4. Find your account identifier: click your name at bottom left, then your account, then "View account details". It looks like `ABCDEFG-XY12345`.
5. Create `~/.snowflake/connections.toml` with this content, then run `chmod 600 ~/.snowflake/connections.toml`. Type `echo $HOME` to get your home folder path.
   ```
   [marlow]
   account = "ABCDEFG-XY12345"
   user = "YOUR_USERNAME"
   authenticator = "SNOWFLAKE_JWT"
   private_key_file = "/Users/YOUR_MAC_NAME/.snowflake/marlow_key.p8"
   role = "ACCOUNTADMIN"
   ```
6. Back in the project folder, install the real connector: `pip install -r requirements.txt`.

Never paste the key file or the toml file into the thread.

## Part 3: run it

```
python run.py setup
python run.py load data/batch_2026_09
python run.py load data/batch_2026_10
python run.py load data/batch_2026_09
```

Each load prints the answers and a pass or fail line per criterion, and saves everything in `results/`. The last command loads September a second time on purpose: criterion 5 passes only if nothing is added.

If anything fails, paste the terminal output (not the keys) in the thread and stop there.

The next morning: `python run.py usage`.

Then open `sql/demo_new_bid.sql` in a Snowsight worksheet and run it. It runs as the director's role, which is what the recording shows.

## Part 4: the 3-minute recording

| Time | What's on screen | What you say |
|---|---|---|
| 0:00 to 0:20 | SUCCESS_CRITERIA.md | The buyer, the problem, and that the criteria were written before the build. Say the data is synthetic |
| 0:20 to 1:00 | Terminal: `python run.py load data/batch_2026_10` | One command per month. Point at the rejects: the unmapped job type, the negative hours. Nothing vanishes |
| 1:00 to 2:00 | Q3 output, then `demo_new_bid.sql` in Snowsight | Two job types win often and overrun: they're winning on price. Then price a new bid the way the director would |
| 2:00 to 2:40 | The criteria table in `results/` | Pass or fail on each line, including any fail. The director's role is refused the raw timesheets. What it cost in credits |
| 2:40 to 3:00 | README | What production would need, in one sentence |

## Questions to be ready for

1. Why load every column as text first?
2. What happens if someone loads the same file twice?
3. How can the director read a view built on tables they have no access to?
4. Why the median overrun and not the average?
5. Why 10% as the overrun line, and who decided it?
6. How would this run every month without you starting it?
7. What did it cost, and what would it cost at ten times the data?
