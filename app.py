from flask import Flask, request, render_template
import sqlparse
import re

app = Flask(__name__)

def split_columns(columns_str):
    """
    Splits a comma-separated list of columns while ignoring commas within
    parentheses or quotes.
    """
    columns = []
    current_col = []
    paren_level = 0
    in_single_quote = False
    in_double_quote = False
    escaped = False
    for char in columns_str:
        if char == "\\":
            escaped = True
            current_col.append(char)
            continue

        if char == "'" and not in_double_quote and not escaped:
            in_single_quote = not in_single_quote
        elif char == '"' and not in_single_quote and not escaped:
            in_double_quote = not in_double_quote
        escaped = False

        if char == '(' and not in_single_quote and not in_double_quote:
            paren_level += 1
        elif char == ')' and not in_single_quote and not in_double_quote:
            if paren_level > 0:
                paren_level -= 1

        if char == ',' and paren_level == 0 and not in_single_quote and not in_double_quote:
            columns.append(''.join(current_col).strip())
            current_col = []
        else:
            current_col.append(char)
    if current_col:
        columns.append(''.join(current_col).strip())
    return columns

def add_column_aliases(sql):
    """
    Adds aliases to columns in the SELECT clause.
    Works on both plain SELECT queries and queries starting with WITH (CTEs).
    """
    # Standardize SQL (remove comments, etc.)
    sql = sqlparse.format(sql, strip_comments=True)

    # Define functions to ignore for aliasing (including NVL and NVL2 now)
    ignored_functions = [
        'COUNT', 'SUM', 'AVG', 'MAX', 'MIN', 
        'STRING_AGG', 'DATE_TRUNC', 'RANK',
        'NVL', 'NVL2', 'SUBSTR', 'TRUNC'
    ]

    # Check if the query starts with a CTE using WITH
    if sql.upper().strip().startswith('WITH'):
        # Attempt to find the main SELECT statement after the CTE(s)
        pattern = r'(\)\s*SELECT\s*)([\s\S]+?)(\s*FROM\s*)'
        match = re.search(pattern, sql, re.IGNORECASE)
        if match:
            before_select = sql[:match.start(1)]
            select_columns = match.group(2)
            after_from = sql[match.end(2):]
            # Process the column list using the new split_columns function
            columns = split_columns(select_columns)
            formatted_columns = []
            for col in columns:
                # Skip if column already has an alias
                if ' AS ' in col.upper():
                    formatted_columns.append(col)
                    continue
                # Skip if it's a function call from the ignored list
                if any(col.upper().startswith(func + '(') for func in ignored_functions):
                    formatted_columns.append(col)
                    continue
                # Add alias for regular table columns
                if '.' in col:
                    table_alias, column_name = col.split('.')
                    formatted_columns.append(f"{table_alias}.{column_name} AS {table_alias}_{column_name}")
                else:
                    formatted_columns.append(col)
            final_sql = (
                before_select +
                ')\nSELECT\n    ' +
                ',\n    '.join(formatted_columns) +
                '\nFROM' +
                after_from
            )
        else:
            final_sql = sql
    # Handle plain SELECT queries (without WITH)
    elif sql.upper().strip().startswith('SELECT'):
        pattern = r'(\bSELECT\b)([\s\S]+?)(\bFROM\b)'
        match = re.search(pattern, sql, re.IGNORECASE)
        if match:
            select_keyword = match.group(1)
            select_columns = match.group(2)
            from_keyword = match.group(3)
            # Process the columns using the new split_columns function
            columns = split_columns(select_columns)
            formatted_columns = []
            for col in columns:
                # Skip if alias already exists
                if ' AS ' in col.upper():
                    formatted_columns.append(col)
                    continue
                # Skip if the column is a function call from the ignored list
                if any(col.upper().startswith(func + '(') for func in ignored_functions):
                    formatted_columns.append(col)
                    continue
                # Add alias if the column follows the table.column pattern
                if '.' in col:
                    parts = col.split('.')
                    if len(parts) == 2:
                        table_alias, column_name = parts
                        formatted_columns.append(f"{table_alias}.{column_name} AS {table_alias}_{column_name}")
                    else:
                        formatted_columns.append(col)
                else:
                    formatted_columns.append(col)
            # Reconstruct the query keeping the FROM clause intact
            before_from = sql[:match.start(3)]
            after_from = sql[match.start(3):]
            final_sql = select_keyword + ' ' + ', '.join(formatted_columns) + ' ' + after_from
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