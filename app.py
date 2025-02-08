from flask import Flask, request, render_template
import sqlparse
import re

app = Flask(__name__)

def add_column_aliases(sql):
    """
    Adds aliases to columns in the main SELECT statement.
    """
    # First, standardize the SQL
    sql = sqlparse.format(sql, strip_comments=True)
    
    if sql.upper().strip().startswith('WITH'):
        # Find the main SELECT statement after all CTEs
        pattern = r'(\)\s*SELECT\s*)([\s\S]*?)(\s*FROM\s*)'
        match = re.search(pattern, sql, re.IGNORECASE)
        
        if match:
            before_select = sql[:match.start(1)]
            select_columns = match.group(2)
            after_from = sql[match.end(2):]
            
            # Process the columns
            columns = [col.strip() for col in select_columns.split(',')]
            formatted_columns = []
            
            for col in columns:
                # Skip if column already has an alias
                if ' AS ' in col.upper():
                    formatted_columns.append(col)
                    continue
                    
                # Skip if it's a function
                if any(col.upper().startswith(func + '(') for func in ['COUNT', 'SUM', 'AVG', 'MAX', 'MIN', 'STRING_AGG', 'DATE_TRUNC', 'RANK']):
                    formatted_columns.append(col)
                    continue
                    
                # Process regular table columns
                if '.' in col:
                    table_alias, column_name = col.split('.')
                    formatted_columns.append(
                        f"{table_alias}.{column_name} AS {table_alias}_{column_name}"
                    )
                else:
                    formatted_columns.append(col)
            
            # Reconstruct the query
            final_sql = (
                before_select + 
                ')\nSELECT\n    ' + 
                ',\n    '.join(formatted_columns) + 
                '\nFROM' + 
                after_from
            )
        else:
            final_sql = sql
    else:
        final_sql = sql
    
    # Final formatting
    formatted_sql = sqlparse.format(
        final_sql,
        reindent=True,
        keyword_case='upper',
        indent_width=4
    )
    
    return formatted_sql

@app.route("/", methods=["GET", "POST"])
def index():
    formatted_sql = ""
    if request.method == "POST":
        raw_sql = request.form["sql"]
        # Format the SQL
        formatted_sql = sqlparse.format(
            raw_sql,
            reindent=True,
            keyword_case="upper",
            indent_width=4
        )
        # Add column aliases only if checkbox is checked
        if request.form.get("add_aliases"):
            formatted_sql = add_column_aliases(formatted_sql)
    return render_template("index.html", formatted_sql=formatted_sql)

if __name__ == "__main__":
    app.run()