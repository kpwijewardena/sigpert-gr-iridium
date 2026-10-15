import zmq
import sqlite3
import struct
import numpy as np

def create_database():
    conn = sqlite3.connect("d_burst_test2.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS iq_data (
            id INTEGER PRIMARY KEY,
            iq BLOB NOT NULL,
            iq_pre BLOB NOT NULL
        )
    """)
    conn.commit()
    return conn

def deserialize_iq_data(data, num_elements):
    return np.frombuffer(data, dtype=np.complex64, count=num_elements)

def write_to_database(conn, id, iq_vector, iq_vector_pre):
    cursor = conn.cursor()
    iq_blob = iq_vector.tobytes()
    iq_pre_blob = iq_vector_pre.tobytes()

    cursor.execute("INSERT OR REPLACE INTO iq_data (id, iq, iq_pre) VALUES (?, ?, ?)", (id, iq_blob, iq_pre_blob))
    conn.commit()

def database_writer():
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

            num_elements = len(iq_data) // (2 * 8)

            iq_vector = deserialize_iq_data(iq_data[:num_elements * 8], num_elements)
            iq_vector_pre = deserialize_iq_data(iq_data[num_elements * 8:num_elements * 16], num_elements)

            write_to_database(conn, id, iq_vector, iq_vector_pre)

            print(f"Data for ID {id} written to database. IQ vector sizes: {len(iq_vector)}, {len(iq_vector_pre)}")
    except KeyboardInterrupt:
        print("\nShutting down database writer...")
    finally:
        conn.close()
        socket.close()
        context.term()

if __name__ == "__main__":
    database_writer()