#!/usr/bin/env python3
"""
Baseline Traffic Generator for IoMT Pump Lab

Generates legitimate pump commands at configurable intervals to establish
a baseline of normal behavior for anomaly detection.

Usage:
    python3 tools/baseline_traffic_gen.py --duration 300 --interval 5
    python3 tools/baseline_traffic_gen.py --host 127.0.0.1 --port 9100 --interval 10

Features:
    - Random realistic flow rates (5-250 mL/h)
    - Configurable command intervals
    - Clean shutdown on Ctrl+C
    - Reuses existing command_client module
    - Logs commands sent for verification
"""

import sys
import time
import random
import argparse
import signal
import logging
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pump.command_client import send_command
from config.settings import PUMP_CMD_HOST, PUMP_CMD_PORT

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [baseline_gen] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("baseline_traffic.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Global flag for clean shutdown
shutdown_event = False


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully."""
    global shutdown_event
    logger.info("\n\nShutdown signal received. Stopping baseline traffic generation.")
    shutdown_event = True


def get_realistic_flow_rate():
    """
    Return a realistic flow rate for medical infusion (mL/h).
    Based on common pump configurations:
    - KVO (Keep Vein Open): 1-5 mL/h
    - Maintenance rate: 10-50 mL/h
    - Bolus rate: 50-250 mL/h
    """
    rand = random.random()
    if rand < 0.3:  # 30% KVO
        return round(random.uniform(1, 5), 1)
    elif rand < 0.7:  # 40% maintenance
        return round(random.uniform(10, 50), 1)
    else:  # 30% bolus
        return round(random.uniform(50, 250), 1)


def send_baseline_command(host, port, command_type):
    """
    Send a single baseline command to the pump.
    Returns True if successful, False otherwise.
    """
    try:
        if command_type == "SET_RATE":
            rate = get_realistic_flow_rate()
            response = send_command(host, port, f"SET_RATE|{rate}")
            logger.info(f"SET_RATE {rate} mL/h -> {response}")
        elif command_type == "PAUSE":
            response = send_command(host, port, "PAUSE")
            logger.info(f"PAUSE -> {response}")
        elif command_type == "RESUME":
            response = send_command(host, port, "RESUME")
            logger.info(f"RESUME -> {response}")
        elif command_type == "STATUS":
            response = send_command(host, port, "STATUS")
            logger.debug(f"STATUS -> {response}")
        return True
    except Exception as e:
        logger.error(f"Failed to send {command_type}: {e}")
        return False


def generate_baseline_traffic(host, port, interval_sec, duration_sec):
    """
    Generate baseline traffic for the specified duration.
    
    Args:
        host: Pump command server hostname/IP
        port: Pump command server port
        interval_sec: Time between commands (seconds)
        duration_sec: Total duration to generate traffic (seconds, 0 = infinite)
    """
    start_time = time.time()
    command_count = 0
    success_count = 0
    error_count = 0
    
    # Command distribution for realistic baseline
    commands = ["SET_RATE"] * 70 + ["PAUSE"] * 10 + ["RESUME"] * 15 + ["STATUS"] * 5
    
    logger.info(f"Starting baseline traffic generation")
    logger.info(f"Target: {host}:{port}")
    logger.info(f"Interval: {interval_sec}s, Duration: {duration_sec}s (0=infinite)")
    logger.info(f"Press Ctrl+C to stop\n")
    
    try:
        while True:
            # Check duration limit
            if duration_sec > 0:
                elapsed = time.time() - start_time
                if elapsed >= duration_sec:
                    break
            
            # Check shutdown flag
            if shutdown_event:
                break
            
            # Send a random command from the distribution
            command = random.choice(commands)
            command_count += 1
            
            if send_baseline_command(host, port, command):
                success_count += 1
            else:
                error_count += 1
            
            # Wait before next command
            time.sleep(interval_sec)
    
    except KeyboardInterrupt:
        logger.info("\n\nKeyboard interrupt received")
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    
    finally:
        elapsed = time.time() - start_time
        logger.info(f"\n" + "="*60)
        logger.info(f"Baseline traffic generation stopped")
        logger.info(f"Total duration: {elapsed:.1f} seconds")
        logger.info(f"Commands sent: {command_count}")
        logger.info(f"Successful: {success_count}")
        logger.info(f"Failed: {error_count}")
        logger.info(f"Average rate: {command_count/elapsed if elapsed > 0 else 0:.2f} cmd/s")
        logger.info(f"="*60)


def main():
    parser = argparse.ArgumentParser(
        description="Generate baseline traffic for IoMT pump lab",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate traffic for 5 minutes with 10-second intervals
  python3 tools/baseline_traffic_gen.py --duration 300 --interval 10
  
  # Generate continuous traffic (Ctrl+C to stop)
  python3 tools/baseline_traffic_gen.py --interval 5
  
  # Connect to remote pump
  python3 tools/baseline_traffic_gen.py --host 192.168.1.100 --port 9100 --interval 15
        """,
    )
    
    parser.add_argument(
        "--host",
        default=PUMP_CMD_HOST,
        help=f"Pump command server host (default: {PUMP_CMD_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=PUMP_CMD_PORT,
        help=f"Pump command server port (default: {PUMP_CMD_PORT})",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=10,
        help="Delay between commands in seconds (default: 10)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=0,
        help="Total duration in seconds (0 = infinite, default: 0)",
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.interval <= 0:
        logger.error("Interval must be positive")
        sys.exit(1)
    
    if args.duration < 0:
        logger.error("Duration must be >= 0")
        sys.exit(1)
    
    # Set up signal handler for clean shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    # Generate baseline traffic
    generate_baseline_traffic(
        host=args.host,
        port=args.port,
        interval_sec=args.interval,
        duration_sec=args.duration,
    )


if __name__ == "__main__":
    main()
