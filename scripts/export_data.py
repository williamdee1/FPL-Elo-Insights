import os
import csv
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

supabase: Client = create_client(url, key)

def fetch_all_records(table_name: str) -> list:
    """Fetches all records from a table using pagination."""
    all_data = []
    page_size = 1000
    start = 0
    
    while True:
        response = (supabase.table(table_name)
                   .select("*")
                   .range(start, start + page_size - 1)
                   .execute())
        
        page_data = response.data
        if not page_data:
            break
            
        all_data.extend(page_data)
        
        if len(page_data) < page_size:
            break
            
        start += page_size
        
    return all_data

def export_table(table_name: str, season: str):
    """Exports a Supabase table to both CSV and SQL formats."""
    try:
        # Fetch all data using pagination
        data = fetch_all_records(table_name)
        
        if not data:
            print(f"No data found in table {table_name}")
            return

        # Create directory structure
        output_dir = os.path.join("data", season, table_name)
        os.makedirs(output_dir, exist_ok=True)
        
        # Export CSV
        csv_file_path = os.path.join(output_dir, f"{table_name}.csv")
        with open(csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
            
        # Export SQL
        sql_file_path = os.path.join(output_dir, f"{table_name}.sql")
        with open(sql_file_path, 'w', encoding='utf-8') as sqlfile:
            # Add timestamp comment
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sqlfile.write(f"-- Data export from {table_name}\n")
            sqlfile.write(f"-- Generated on {timestamp}\n")
            sqlfile.write(f"-- Total records: {len(data)}\n\n")
            
            # Write DROP and CREATE TABLE statements
            sqlfile.write(f"DROP TABLE IF EXISTS {table_name};\n")
            columns = data[0].keys()
            create_table = f"CREATE TABLE {table_name} (\n"
            create_table += ",\n".join(f"    {col} TEXT" for col in columns)
            create_table += "\n);\n\n"
            sqlfile.write(create_table)
            
            # Write INSERT statements in batches
            batch_size = 500
            for i in range(0, len(data), batch_size):
                batch = data[i:i + batch_size]
                for row in batch:
                    values = [str(val).replace("'", "''") if val is not None else 'NULL' for val in row.values()]
                    values_str = ", ".join(f"'{val}'" if val != 'NULL' else val for val in values)
                    insert_stmt = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({values_str});\n"
                    sqlfile.write(insert_stmt)
                
        print(f"Successfully exported {table_name} to CSV and SQL in {output_dir} (Total records: {len(data)})")

    except Exception as e:
        print(f"Error exporting {table_name}: {e}")
        return

def main():
    """Main function to export all tables."""
    season = "2024-2025"
    tables = ["matches", "playermatchstats", "players", "playerstats", "teams"]
    
    for table in tables:
        export_table(table, season)

if __name__ == "__main__":
    main()