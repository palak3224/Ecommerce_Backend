#!/usr/bin/env python3
"""
Server Startup Script
This script can start both the main e-commerce backend and live streaming server.
"""

import os
import sys
import subprocess
import time
import signal
import threading
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def start_main_backend():
    """Start the main e-commerce backend server."""
    print("🚀 Starting Main E-commerce Backend...")
    try:
        # Change to the main backend directory
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        
        # Start the main backend
        process = subprocess.Popen([
            sys.executable, "app.py"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        print(f"✅ Main Backend started with PID: {process.pid}")
        return process
    except Exception as e:
        print(f"❌ Error starting main backend: {e}")
        return None

def start_live_streaming_server():
    """Start the live streaming server."""
    print("🎥 Starting Live Streaming Server...")
    try:
        # Change to the live streaming server directory
        live_streaming_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "live_streaming_server")
        os.chdir(live_streaming_dir)
        
        # Start the live streaming server
        process = subprocess.Popen([
            sys.executable, "run_server.py"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        print(f"✅ Live Streaming Server started with PID: {process.pid}")
        return process
    except Exception as e:
        print(f"❌ Error starting live streaming server: {e}")
        return None

def monitor_process(process, name):
    """Monitor a process and print its output."""
    while process.poll() is None:
        output = process.stdout.readline()
        if output:
            print(f"[{name}] {output.decode().strip()}")
    
    # Print any remaining output
    remaining_output, remaining_error = process.communicate()
    if remaining_output:
        print(f"[{name}] {remaining_output.decode()}")
    if remaining_error:
        print(f"[{name} ERROR] {remaining_error.decode()}")

def main():
    """Main function to start both servers."""
    print("=" * 60)
    print("🛍️  AOIN E-commerce Server Manager")
    print("=" * 60)
    
    # Check if we should start both servers
    start_both = input("Start both servers? (y/n): ").lower().strip() == 'y'
    
    if start_both:
        print("\n🔄 Starting both servers...")
        
        # Start main backend
        main_backend = start_main_backend()
        if not main_backend:
            print("❌ Failed to start main backend. Exiting.")
            return
        
        # Wait a moment for the main backend to initialize
        time.sleep(2)
        
        # Start live streaming server
        live_streaming = start_live_streaming_server()
        if not live_streaming:
            print("❌ Failed to start live streaming server.")
            print("🛑 Stopping main backend...")
            main_backend.terminate()
            return
        
        print("\n✅ Both servers started successfully!")
        print("=" * 60)
        print("📍 Main Backend: http://localhost:5000")
        print("🎥 Live Streaming: http://localhost:5001")
        print("📚 API Documentation: http://localhost:5000/docs")
        print("💚 Health Check: http://localhost:5001/health")
        print("=" * 60)
        print("Press Ctrl+C to stop both servers")
        
        # Start monitoring threads
        main_thread = threading.Thread(target=monitor_process, args=(main_backend, "Main Backend"))
        live_thread = threading.Thread(target=monitor_process, args=(live_streaming, "Live Streaming"))
        
        main_thread.daemon = True
        live_thread.daemon = True
        
        main_thread.start()
        live_thread.start()
        
        try:
            # Keep the main thread alive
            while main_backend.poll() is None and live_streaming.poll() is None:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping servers...")
            main_backend.terminate()
            live_streaming.terminate()
            
            # Wait for processes to terminate
            main_backend.wait()
            live_streaming.wait()
            
            print("✅ Servers stopped successfully")
    
    else:
        # Start individual server
        print("\nWhich server would you like to start?")
        print("1. Main E-commerce Backend")
        print("2. Live Streaming Server")
        
        choice = input("Enter your choice (1 or 2): ").strip()
        
        if choice == "1":
            process = start_main_backend()
            if process:
                print("✅ Main Backend started!")
                print("📍 URL: http://localhost:5000")
                print("📚 API Documentation: http://localhost:5000/docs")
                print("Press Ctrl+C to stop")
                
                try:
                    monitor_process(process, "Main Backend")
                except KeyboardInterrupt:
                    process.terminate()
                    print("\n✅ Main Backend stopped")
        
        elif choice == "2":
            process = start_live_streaming_server()
            if process:
                print("✅ Live Streaming Server started!")
                print("📍 URL: http://localhost:5001")
                print("💚 Health Check: http://localhost:5001/health")
                print("Press Ctrl+C to stop")
                
                try:
                    monitor_process(process, "Live Streaming")
                except KeyboardInterrupt:
                    process.terminate()
                    print("\n✅ Live Streaming Server stopped")
        
        else:
            print("❌ Invalid choice")

if __name__ == '__main__':
    main() 