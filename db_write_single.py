import zmq
import sqlite3
import struct
import numpy as np

def create_database():
    """
    Creates the SQLite database and the `iq_data` table if it doesn't already exist.
    """
    conn = sqlite3.connect("d_burst_test.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS iq_data (
            id INTEGER PRIMARY KEY,
            iq BLOB NOT NULL
        )
    """)
    conn.commit()
    return conn

def deserialize_iq_data(data, num_elements):
    """
    Deserializes the IQ vector data from the raw bytes received from ZeroMQ.
    """
    return np.frombuffer(data, dtype=np.complex64, count=num_elements)

def write_to_database(conn, id, iq_vector):
    """
    Writes the received data into the SQLite database.
    """
    cursor = conn.cursor()
    iq_blob = iq_vector.tobytes()
    
    cursor.execute("INSERT OR REPLACE INTO iq_data (id, iq) VALUES (?, ?)", (id, iq_blob))
    conn.commit()

def database_writer():
    """
    Listens on a ZeroMQ socket for incoming messages and writes them to the SQLite database.
    """
    conn = create_database()

    context = zmq.Context()
    socket = context.socket(zmq.PULL)
    socket.bind("tcp://127.0.0.1:5555")

    print("Database writer is running and listening for incoming data...")

    try:
        while True:
            message = socket.recv()

            id = struct.unpack("i", message[:4])[0]
            iq_data = message[4:]

            # Determine the number of elements in each IQ vector
            num_elements_total = len(iq_data) // (2 * 4)  # Each complex64 is 8 bytes

            iq_vector = deserialize_iq_data(iq_data[:num_elements_total * 8], num_elements_total)

            write_to_database(conn, id, iq_vector)

            print(f"Data for ID {id} written to database. IQ vector sizes: {len(iq_vector)}")
    except KeyboardInterrupt:
        print("\nShutting down database writer...")
    finally:
        conn.close()
        socket.close()
        context.term()

if __name__ == "__main__":
    database_writer()
