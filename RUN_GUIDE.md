# Run guide

How to run the proof of concept: first on a local emulator, then on a Snowflake trial account. A trial lasts 30 days from sign-up, so do part 1 before you sign up.

## Part 1: rehearse locally (no account needed)

From this folder, in a terminal:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-local.txt
python tests/test_local.py
```

It should end with "All testable criteria pass on the emulator". The emulator can't test roles or credits, so criteria 6 and 7 show as SKIP.

Emulator result files have `local` in their names. They are never Snowflake results.

## Part 2: sign up and connect

1. Sign up at signup.snowflake.com. Choose **Enterprise** edition, **AWS**, region **Europe (London)**. Don't add a card. AI features stay off without one, and this build doesn't use them.
2. Make a key pair in your terminal. The private key never leaves your machine:
   ```
   mkdir -p ~/.snowflake && cd ~/.snowflake
   openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out marlow_key.p8 -nocrypt
   openssl rsa -in marlow_key.p8 -pubout -out marlow_key.pub
   chmod 600 marlow_key.p8
   grep -v "PUBLIC KEY" marlow_key.pub | tr -d '\n'; echo
   ```
   The key has no passphrase and is protected by file permissions only. That is a fair trade for a trial account holding synthetic data. With real data, give the key a passphrase or keep it in a secrets manager.
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
   `ACCOUNTADMIN` is needed for the first setup only, because the pipeline's own role doesn't exist yet. Step 2 of part 3 changes it.
6. Back in the project folder, install the real connector: `pip install -r requirements.txt`.

Never share or commit the key file or the toml file. `.gitignore` already excludes both.

## Part 3: run it

1. Create the roles, warehouse and database:
   ```
   python run.py setup
   ```
2. Open `~/.snowflake/connections.toml` and change the last line to `role = "MARLOW_ADMIN"`. From now on a new session starts with the pipeline's role, not as account admin. `sql/01_setup.sql` switches to `ACCOUNTADMIN` by itself if setup is ever run again.
3. Load the two months, then September a second time:
   ```
   python run.py load data/batch_2026_09
   python run.py load data/batch_2026_10
   python run.py load data/batch_2026_09
   ```

Each load prints the answers and a pass or fail line per criterion, and saves everything in `results/`. The last command loads September a second time on purpose: criterion 5 passes only if nothing is added.

If a command fails, stop there and read the error before running the next one. Each command is safe to run again.

For the credit figure, run `python run.py usage` at least 6 hours after the last load. Snowflake's metering lags by up to 3 hours for compute and up to 6 for cloud services. The figure is the warehouse's total to date, so it grows with every later query.

To see the answers as the director would, open `sql/demo_new_bid.sql` in a Snowsight worksheet and run it. It runs under the director's role.

## After the trial

The trial account closes 30 days after sign-up. Everything rebuilds on a fresh account with the same commands.
