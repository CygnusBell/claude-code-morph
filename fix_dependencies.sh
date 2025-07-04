#!/bin/bash

# Fix Dependencies Script for Claude Code Morph
# This script helps resolve installation issues, particularly for Python 3.13 compatibility

set -e

echo "🔧 Claude Code Morph - Dependency Installation Helper"
echo "===================================================="

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

echo -e "\n📌 Python version detected: ${GREEN}$PYTHON_VERSION${NC}"

# Warning for Python 3.13
if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 13 ]; then
    echo -e "${YELLOW}⚠️  Warning: Python 3.13 detected. Some packages may not be fully compatible yet.${NC}"
    echo -e "${YELLOW}   Consider using Python 3.12 or earlier for best compatibility.${NC}"
fi

# Check for system dependencies
echo -e "\n🔍 Checking system dependencies..."

check_command() {
    if command -v $1 &> /dev/null; then
        echo -e "  ✅ $1 is installed"
        return 0
    else
        echo -e "  ❌ $1 is NOT installed"
        return 1
    fi
}

# Check required system packages
MISSING_DEPS=()
check_command cmake || MISSING_DEPS+=("cmake")
check_command pkg-config || MISSING_DEPS+=("pkg-config")
check_command gcc || MISSING_DEPS+=("gcc")
check_command g++ || MISSING_DEPS+=("g++")

# Install missing system dependencies
if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    echo -e "\n${YELLOW}📦 Missing system dependencies detected. Installing...${NC}"
    
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Detect Linux distribution
        if [ -f /etc/debian_version ]; then
            echo "Detected Debian/Ubuntu system"
            echo "Installing: ${MISSING_DEPS[*]}"
            sudo apt-get update
            sudo apt-get install -y build-essential cmake pkg-config
        elif [ -f /etc/redhat-release ]; then
            echo "Detected RedHat/CentOS/Fedora system"
            sudo yum install -y gcc gcc-c++ cmake pkgconfig
        elif [ -f /etc/arch-release ]; then
            echo "Detected Arch Linux"
            sudo pacman -S --needed base-devel cmake pkg-config
        else
            echo -e "${RED}❌ Unsupported Linux distribution. Please install manually:${NC}"
            echo "   - cmake"
            echo "   - pkg-config"
            echo "   - gcc/g++ (build-essential)"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "Detected macOS"
        if command -v brew &> /dev/null; then
            brew install cmake pkg-config
        else
            echo -e "${RED}❌ Homebrew not found. Please install Homebrew first:${NC}"
            echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        fi
    else
        echo -e "${RED}❌ Unsupported operating system: $OSTYPE${NC}"
    fi
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo -e "\n📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo -e "\n🔄 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip, setuptools, and wheel
echo -e "\n📦 Upgrading pip, setuptools, and wheel..."
pip install --upgrade pip setuptools wheel

# Install packages with specific handling
echo -e "\n📦 Installing Python packages..."

# Function to install package with fallback
install_package() {
    local package=$1
    local fallback=$2
    
    echo -e "\n  Installing $package..."
    if pip install "$package" 2>/dev/null; then
        echo -e "  ✅ $package installed successfully"
    else
        echo -e "  ${YELLOW}⚠️  Failed to install $package${NC}"
        if [ -n "$fallback" ]; then
            echo -e "  🔄 Trying fallback: $fallback"
            pip install "$fallback"
        fi
    fi
}

# Install packages one by one with specific handling
install_package "textual==0.47.1"
install_package "rich==13.7.0"
install_package "pyyaml==6.0.1"
install_package "groq==0.4.2"
install_package "openai==1.12.0"
install_package "anthropic==0.18.0"
install_package "asyncio==3.4.3"
install_package "watchdog==4.0.0"
install_package "pyperclip==1.8.2"
install_package "pexpect==4.9.0"
install_package "pyte==0.8.2"

# Handle problematic packages
echo -e "\n🔧 Installing packages that may need special handling..."

# ChromaDB - may have issues with certain dependencies
echo -e "\n  Installing ChromaDB..."
pip install chromadb==0.4.22 || {
    echo -e "  ${YELLOW}⚠️  ChromaDB installation failed. Trying with no-cache...${NC}"
    pip install --no-cache-dir chromadb==0.4.22
}

# Sentence Transformers - requires sentencepiece which needs cmake
echo -e "\n  Installing sentence-transformers..."
pip install sentencepiece || {
    echo -e "  ${YELLOW}⚠️  sentencepiece failed. Installing from source...${NC}"
    pip install --no-binary :all: sentencepiece
}
pip install sentence-transformers==2.2.2

# PyPDF
echo -e "\n  Installing pypdf..."
install_package "pypdf==3.17.4"

# Tiktoken - known issues with Python 3.13
echo -e "\n  Installing tiktoken..."
if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 13 ]; then
    echo -e "  ${YELLOW}⚠️  tiktoken may not support Python 3.13 yet${NC}"
    echo -e "  🔄 Attempting installation anyway..."
    pip install tiktoken==0.5.2 || {
        echo -e "  ${RED}❌ tiktoken installation failed${NC}"
        echo -e "  ${YELLOW}💡 Alternatives:${NC}"
        echo -e "     1. Use Python 3.12 or earlier"
        echo -e "     2. Try installing from source: pip install git+https://github.com/openai/tiktoken.git"
        echo -e "     3. Use alternative tokenizer libraries"
    }
else
    install_package "tiktoken==0.5.2"
fi

# Final check
echo -e "\n🔍 Verifying installation..."
python3 -c "
import sys
print(f'Python {sys.version}')
try:
    import textual; print('✅ textual')
    import rich; print('✅ rich')
    import yaml; print('✅ pyyaml')
    import groq; print('✅ groq')
    import openai; print('✅ openai')
    import anthropic; print('✅ anthropic')
    import watchdog; print('✅ watchdog')
    import pyperclip; print('✅ pyperclip')
    import pexpect; print('✅ pexpect')
    import pyte; print('✅ pyte')
    import chromadb; print('✅ chromadb')
    import sentence_transformers; print('✅ sentence-transformers')
    import pypdf; print('✅ pypdf')
    try:
        import tiktoken; print('✅ tiktoken')
    except:
        print('⚠️  tiktoken (optional, may not work with Python 3.13)')
except ImportError as e:
    print(f'❌ Failed to import: {e}')
"

echo -e "\n✨ Installation script completed!"
echo -e "\n📝 Next steps:"
echo -e "  1. Activate the virtual environment: ${GREEN}source venv/bin/activate${NC}"
echo -e "  2. Run the application: ${GREEN}python main.py${NC}"

if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 13 ]; then
    echo -e "\n${YELLOW}⚠️  Python 3.13 Compatibility Note:${NC}"
    echo -e "  If you encounter issues, consider using pyenv or conda to install Python 3.12:"
    echo -e "  ${GREEN}pyenv install 3.12.0${NC}"
    echo -e "  ${GREEN}pyenv local 3.12.0${NC}"
fi