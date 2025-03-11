# PDF Studio

A high-performance professional PDF processing application combining the power of C++ with the simplicity of a Flask web interface.

## Features

PDF Studio offers a complete suite of tools to manipulate your PDF files:

- ✅ **Merge PDF**: combine multiple PDF files into a single document
- ✅ **Split PDF**: extract specific pages or split into multiple files
- ✅ **Compress PDF**: reduce the size of PDF files while maintaining quality
- ✅ **Rotate PDF**: rotate pages at different angles
- ✅ **Add Watermark**: add a text watermark to your documents
- ✅ **Protect/Unlock PDF**: add or remove password protection
- ✅ **Extract Information**: analyze and extract metadata from PDFs

_And much more..._

## Architecture

PDF Studio uses a modern architecture that clearly separates the front-end and back-end:

- **Presentation Layer**: Simple and intuitive HTML/CSS/JS user interface
- **API Layer**: RESTful Flask API to handle requests
- **Processing Layer**: High-performance C++ engine based on PoDoFo for PDF processing
- **Storage Layer**: Local storage to ensure data sovereignty

## Installation with Docker (recommended)

Installation with Docker is simple and works on all systems (Windows, macOS, Linux):

```bash
# Clone the repository
git clone https://github.com/your-username/pdf-studio.git
cd pdf-studio

# Run the installation script
chmod +x install.sh
./install.sh
```

The application will be available at: http://localhost:5000

## Manual Installation (development)

### Prerequisites

- Python 3.8+
- G++ with C++14 support
- PoDoFo library

### Installation Steps

```bash
# Install system dependencies
## On Debian/Ubuntu
sudo apt-get update && sudo apt-get install -y build-essential g++ make cmake libpodofo-dev

## On macOS with Homebrew
brew install cmake podofo

# Install Python dependencies
pip install -r requirements.txt

# Compile the C++ tool
cd cppeditor && make && cd ..

# Create data directories
mkdir -p data/uploads data/temp data/processed

# Launch the application
flask run
```

## Development

The project structure is organized as follows:

```
pdf-studio/
├── app/                  # Flask Application
│   ├── api/              # RESTful API
│   ├── static/           # Static files (CSS, JS)
│   ├── templates/        # HTML Templates
│   └── routes.py         # Main routes
├── cppeditor/            # C++ tool for PDF processing
│   ├── src/              # C++ source code
│   └── Makefile          # Compilation instructions
├── data/                 # Local file storage
│   ├── uploads/          # Uploaded files
│   ├── temp/             # Temporary files
│   └── processed/        # Processed files
├── Dockerfile            # Docker configuration
├── requirements.txt      # Python dependencies
└── install.sh            # Installation script
```

## Data Sovereignty

All files are processed locally. No data is sent to external servers, thus ensuring complete confidentiality of your documents.

## Contribution

Contributions are welcome! Feel free to open an issue or submit a pull request.

## License

This project is under the MIT license. See the LICENSE file for more details. 