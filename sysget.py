import requests
import os
from urllib.parse import urljoin, unquote, urlparse
from bs4 import BeautifulSoup
from tqdm import tqdm
import platform
import signal
import sys
from colorama import Fore, Style, init
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Initialize colorama for cross-platform colored output
init()

# Allowed file extensions (customizable for course materials)
ALLOWED_EXTENSIONS = {'.mp4', '.wmv', '.pdf', '.zip', '.bat', '.sh', '.sql', '.plb', '.jpg', '.gif', '.png', '.doc', '.mht'}

# Maximum number of parallel downloads
MAX_WORKERS = 4  # Adjust based on your system/internet; 4 is a good balance

def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if platform.system() == 'Windows' else 'clear')

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    clear_screen()
    print(Fore.CYAN + "SysEternals: Exiting gracefully..." + Style.RESET_ALL)
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def print_entry_screen():
    """Display the SysEternals entry screen with ASCII art."""
    clear_screen()
    current_time = datetime.now().strftime("%I:%M %p %Z on %A, %B %d, %Y")
    print(Fore.CYAN + Style.BRIGHT + """
/$$$$$$                      /$$$$$$$$ /$$                                             /$$          
/$$__  $$                    | $$_____/| $$                                            | $$          
| $$  \__/ /$$   /$$  /$$$$$$$| $$     /$$$$$$    /$$$$$$   /$$$$$$  /$$$$$$$   /$$$$$$ | $$  /$$$$$$$
|  $$$$$$ | $$  | $$ /$$_____/| $$$$$ |_  $$_/   /$$__  $$ /$$__  $$| $$__  $$ |____  $$| $$ /$$_____/
 \____  $$| $$  | $$|  $$$$$$ | $$__/   | $$    | $$$$$$$$| $$  \__/| $$  \ $$  /$$$$$$$| $$|  $$$$$$ 
 /$$  \ $$| $$  | $$ \____  $$| $$      | $$ /$$| $$_____/| $$      | $$  | $$ /$$__  $$| $$ \____  $$
|  $$$$$$/|  $$$$$$$ /$$$$$$$/| $$$$$$$$|  $$$$/|  $$$$$$$| $$      | $$  | $$|  $$$$$$$| $$ /$$$$$$$/
 \______/  \____  $$|_______/ |________/ \___/   \_______/|__/      |__/  |__/ \_______/|__/|_______/ 
           /$$  | $$                                                                                  
          |  $$$$$$/                                                                                  
           \______/
""" + Fore.YELLOW + "SysEternals Directory Downloader" + Fore.CYAN + """
Version 1.0 | Created for efficient course material downloads
---------------------------------------------------------------
Features:
 • Downloads files (e.g., .mp4, .pdf) from directory URLs
 • Skips parent directories and HTML pages
 • Minimal progress bar and error logging
 • Optimized for faster downloads with parallel processing
---------------------------------------------------------------
System: Today's date and time is """ + current_time + """
---------------------------------------------------------------
""" + Style.RESET_ALL)

def log_error(category, error_type, error_message):
    """Log errors to a file."""
    with open('syseternals_errors.log', 'a') as error_file:
        error_file.write(f"[SysEternals ERROR] {category}: {error_type} - {error_message}\n")

def download_file(url, folder):
    """Download a file from a URL to the specified folder with a minimal progress bar."""
    try:
        # Extract file name
        file_name = unquote(os.path.basename(urlparse(url).path))
        if not file_name:
            print(Fore.RED + f"[SysEternals]: Skipping {url}: No valid file name." + Style.RESET_ALL)
            return

        # Check if file extension is allowed
        ext = os.path.splitext(file_name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            print(Fore.YELLOW + f"[SysEternals]: Skipping {file_name}: Extension {ext} not in allowed list." + Style.RESET_ALL)
            return

        # Create full file path
        file_path = os.path.join(folder, file_name)

        # Check if file already exists
        if os.path.exists(file_path):
            print(Fore.YELLOW + f"[SysEternals]: Skipping {file_name}: File already exists." + Style.RESET_ALL)
            return

        # Check file size
        response = requests.head(url, timeout=10)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))

        # Download file with minimal progress bar
        with requests.get(url, stream=True, allow_redirects=False, timeout=10) as response:
            response.raise_for_status()
            print(Fore.GREEN + f"[SysEternals]: Downloading {file_name}" + Style.RESET_ALL)
            
            with open(file_path, 'wb') as file, tqdm(
                desc=file_name,
                total=total_size,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
                bar_format='[{bar:20}] {percentage:3.0f}% | {rate_fmt}'  # Minimal [------] style
            ) as progress_bar:
                for chunk in response.iter_content(chunk_size=131072):  # Increased chunk size for speed
                    if chunk:
                        file.write(chunk)
                        progress_bar.update(len(chunk))
            
            print(Fore.GREEN + f"[SysEternals]: Downloaded successfully: {file_path}" + Style.RESET_ALL)

    except requests.exceptions.HTTPError as e:
        log_error("Download", "HTTP Error", f"{url}: {e}")
        print(Fore.RED + f"[SysEternals]: HTTP Error downloading {file_name}: {e}" + Style.RESET_ALL)
    except requests.exceptions.ConnectionError as e:
        log_error("Download", "Connection Error", f"{url}: {e}")
        print(Fore.RED + f"[SysEternals]: Connection Error downloading {file_name}: {e}" + Style.RESET_ALL)
    except requests.exceptions.Timeout:
        log_error("Download", "Timeout", f"{url}: Request timed out")
        print(Fore.RED + f"[SysEternals]: Timeout downloading {file_name}" + Style.RESET_ALL)
    except Exception as e:
        log_error("Download", "Unexpected Error", f"{url}: {e}")
        print(Fore.RED + f"[SysEternals]: Unexpected Error downloading {file_name}: {e}" + Style.RESET_ALL)

def process_directory(url, parent_folder):
    """Recursively process a directory and download its files in parallel."""
    try:
        # Fetch directory listing
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract folder name
        decoded_folder = unquote(os.path.basename(urlparse(url).path.rstrip('/')))
        if not decoded_folder or decoded_folder in {'Cursos', '..', '.', ''}:
            print(Fore.YELLOW + f"[SysEternals]: Skipping directory: {decoded_folder or 'root'}" + Style.RESET_ALL)
            return

        # Create folder path
        folder = os.path.join(parent_folder, decoded_folder)
        if not os.path.exists(folder):
            os.makedirs(folder)

        # Collect files and subdirectories
        files_to_download = []
        subdirectories = []

        for link in soup.find_all('a'):
            href = link.get('href')
            if not href:
                continue

            full_url = urljoin(url, href)
            parsed_href = urlparse(full_url).path

            # Check if it's a directory
            if (link.find_previous('img', alt="[DIR]") or 
                link.find_previous('img', alt="[Directorio]") or 
                href.endswith('/')):
                # Skip parent or restricted directories
                if href in {'../', './', '/'} or 'Cursos' in href:
                    print(Fore.YELLOW + f"[SysEternals]: Skipping parent/root directory: {href}" + Style.RESET_ALL)
                    continue
                subdirectories.append((full_url, folder))
            elif os.path.splitext(parsed_href)[1].lower() in ALLOWED_EXTENSIONS:
                files_to_download.append((full_url, folder))

        # Download files in parallel
        if files_to_download:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                future_to_url = {executor.submit(download_file, url, folder): url for url, folder in files_to_download}
                for future in as_completed(future_to_url):
                    future.result()  # Wait for completion, errors are handled in download_file

        # Process subdirectories recursively
        for sub_url, sub_folder in subdirectories:
            process_directory(sub_url, sub_folder)

        print(Fore.GREEN + f"[SysEternals]: Finished processing directory: {folder}" + Style.RESET_ALL)

    except requests.exceptions.HTTPError as e:
        log_error("Directory", "HTTP Error", f"{url}: {e}")
        print(Fore.RED + f"[SysEternals]: HTTP Error processing {url}: {e}" + Style.RESET_ALL)
    except requests.exceptions.ConnectionError as e:
        log_error("Directory", "Connection Error", f"{url}: {e}")
        print(Fore.RED + f"[SysEternals]: Connection Error processing {url}: {e}" + Style.RESET_ALL)
    except requests.exceptions.Timeout:
        log_error("Directory", "Timeout", f"{url}: Request timed out")
        print(Fore.RED + f"[SysEternals]: Timeout processing {url}" + Style.RESET_ALL)
    except Exception as e:
        log_error("Directory", "Unexpected Error", f"{url}: {e}")
        print(Fore.RED + f"[SysEternals]: Unexpected Error processing {url}: {e}" + Style.RESET_ALL)

def main():
    """Main function to start the downloader."""
    print_entry_screen()
    base_url = input(Fore.CYAN + "[SysEternals]: Enter the directory URL to download: " + Style.RESET_ALL).strip()
    if not base_url:
        print(Fore.RED + "[SysEternals]: Error: No URL provided." + Style.RESET_ALL)
        return

    parent_folder = input(Fore.CYAN + "[SysEternals]: Enter save directory (default: 'downloads'): " + Style.RESET_ALL).strip() or "downloads"
    process_directory(base_url, parent_folder)
    print(Fore.GREEN + "[SysEternals]: All directories processed successfully." + Style.RESET_ALL)

if __name__ == "__main__":
    main()
