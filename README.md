# Blockendance

A blockchain-based attendance management system built in Python with a Flask web interface.

## Description

Blockendance implements a basic blockchain from scratch to record and manage class attendance. Each attendance session is stored as a block containing a SHA-256 hash of its data and a reference to the previous block's hash, forming an immutable chain. The system provides a web interface to add attendance records, view blocks, search records, verify chain integrity, and export data.

## Technologies

- Python 3.6+
- Flask
- SHA-256 (via Python's `hashlib`)
- JSON (local file storage)
- HTML / CSS (Materialize Design)

## Features

- Create a genesis block to initialize the blockchain
- Add new attendance blocks with class, date, and student data
- Verify chain integrity by checking hashes and block linkage
- Search attendance records by student, class, or date
- View individual blocks and full transaction history
- Export attendance data to CSV
- Persist blockchain to a local JSON file with automatic backups
- Basic analytics and attendance reports

## File Structure

```
Blockendance/
├── block.py          # Block class: hashing and validation
├── genesis.py        # Genesis block creation
├── newBlock.py       # Adding new blocks to the chain
├── getBlock.py       # Block retrieval and search
├── checkChain.py     # Chain integrity verification
├── persistence.py    # Save/load blockchain to JSON
├── analytics.py      # Attendance analytics and reporting
├── blockchain.py     # Flask application and routes
└── templates/        # HTML templates for the web interface
```

## How to Run

**Requirements:** Python 3.6+, pip

1. Clone the repository:
   ```bash
   git clone https://github.com/atharvakonde10-web/Blockendance.git
   cd Blockendance
   ```

2. Install dependencies:
   ```bash
   pip install Flask
   ```

3. Run the application:
   ```bash
   python blockchain.py
   ```

4. Open your browser and go to `http://localhost:5001`

## Storage

Blockchain data is saved to `blockchain_data.json` in the project directory. Automatic backups are written to the `blockchain_backups/` folder on each save. Both are excluded from version control via `.gitignore`.

## Limitations

- Single-node only — no peer-to-peer networking or distributed consensus
- No proof-of-work or mining
- No smart contracts
- Data is stored locally in a JSON file, not on a distributed ledger
- Intended for educational and demonstration use

## License

MIT License — see [LICENSE](LICENSE) for details.
