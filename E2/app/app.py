#!/usr/bin/python3
# Copyright (c) BDist Development Team
# Distributed under the terms of the Modified BSD License.
import os
import time
from logging.config import dictConfig

from flask import Flask, jsonify, request
from psycopg.rows import namedtuple_row
from psycopg_pool import ConnectionPool


# Use the DATABASE_URL environment variable if it exists, otherwise use the default.
# Use the format postgres://username:password@hostname/database_name to connect to the database.
DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://saude:saude@postgres/saude")

pool = ConnectionPool(
    conninfo=DATABASE_URL,
    kwargs={
        "autocommit": True,  # If True don’t start transactions automatically.
        "row_factory": namedtuple_row,
    },
    min_size=4,
    max_size=10,
    open=True,
    # check=ConnectionPool.check_connection,
    name="postgres_pool",
    timeout=5,
)

dictConfig(
    {
        "version": 1,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] %(levelname)s in %(module)s:%(lineno)s - %(funcName)20s(): %(message)s",
            }
        },
        "handlers": {
            "wsgi": {
                "class": "logging.StreamHandler",
                "stream": "ext://flask.logging.wsgi_errors_stream",
                "formatter": "default",
            }
        },
        "root": {"level": "INFO", "handlers": ["wsgi"]},
    }
)

app = Flask(__name__)
app.config.from_prefixed_env()
log = app.logger


# Funções auxiliares
def is_decimal(s):
    """Returns True if string is a parseable float number."""
    try:
        float(s)
        return True
    except ValueError:
        return False
    
def is_int(s):
    """Returns True if string is a parseable integer number."""
    try:
        int(s)
        return True
    except ValueError:
        return False
    
def is_ssn(s):
    """Returns True if string is a parseable ssn number."""
    if is_int(s) and len(s) == 11 :
        return True
    else:
        return False
    
def is_nif(s):
    """Returns True if string is a parseable nif number."""
    if is_int(s) and len(s) == 9 :
        return True
    else:
        return False
    
def is_data(s):
    """
    Returns True if the string is a parseable date in the format '%Y-%m-%d'.
    
    Args:
    s (str): The string to check.
    
    Returns:
    bool: True if s is a valid date, False otherwise.
    """
    parts = s.split('-')
    if len(parts) != 3:
        return False
    
    year, month, day = parts
    if not (year.isdigit() and month.isdigit() and day.isdigit()):
        return False

    year = int(year)
    month = int(month)
    day = int(day)
    
    if year < 1 or month < 1 or month > 12:
        return False
    
    # Verifica o número de dias em cada mês
    if month in {1, 3, 5, 7, 8, 10, 12}:
        return 1 <= day <= 31
    elif month in {4, 6, 9, 11}:
        return 1 <= day <= 30
    elif month == 2:
        # Verifica ano bissexto
        if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
            return 1 <= day <= 29
        else:
            return 1 <= day <= 28

    return False
    
def is_hora(s):
    """
    Returns True if the string is a parseable time in the format '%H:%M:%S'.
    
    Args:
    s (str): The string to check.
    
    Returns:
    bool: True if s is a valid time, False otherwise.
    """
    parts = s.split(':')
    if len(parts) != 3:
        return False
    
    hour, minute, second = parts
    if not (hour.isdigit() and minute.isdigit() and second.isdigit()):
        return False

    hour = int(hour)
    minute = int(minute)
    second = int(second)

    return (0 <= hour < 24) and (0 <= minute < 60) and (0 <= second < 60)

def is_future_date_and_time(date_str, time_str):
    """
    Check if the given date and time are in the future compared to the current date and time.

    """
    if not is_data(date_str) or not is_hora(time_str):
        return False

    # Obter a data e hora atuais
    now = time.localtime()
    current_year = now.tm_year
    current_month = now.tm_mon
    current_day = now.tm_mday
    current_hour = now.tm_hour
    current_minute = now.tm_min
    current_second = now.tm_sec

    # Dividir a string de data e hora fornecidas
    year, month, day = map(int, date_str.split('-'))
    hour, minute, second = map(int, time_str.split(':'))

    # Comparar data
    if year > current_year:
        return True
    elif year == current_year:
        if month > current_month:
            return True
        elif month == current_month:
            if day > current_day:
                return True
            elif day == current_day:
                # Comparar hora
                if hour > current_hour:
                    return True
                elif hour == current_hour:
                    if minute > current_minute:
                        return True
                    elif minute == current_minute:
                        if second > current_second:
                            return True
    return False


 
@app.route("/", methods=("GET",))

def list_clinics():
    """lists the name and address of all clinics"""

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute( 
                """
                SELECT nome, morada
                FROM clinica;
                """
            )
            clinicas = cur.fetchall()
            log.debug(f"Found {cur.rowcount} rows.")

            if cur.rowcount == 0:
                return jsonify({"message": "No clinics found.", "status": "error"}), 404

    return jsonify(clinicas), 200

#responsavel por listar todas as especialidades de uma clinica da base de dados saude
@app.route("/c/<clinica>", methods=("GET",))
def list_specialties(clinica):
    """lists the name of all specialties"""

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM clinica
                WHERE nome = %(nome)s;
                """,
                {"nome": clinica}
            )

            if cur.rowcount == 0:
                return_msg = f"Clinic: {clinica} not found."
                return jsonify({"message": return_msg, "status": "error"}), 404

            cur.execute( 
                """
                SELECT DISTINCT 
                    especialidade
                FROM 
                    medico JOIN trabalha ON medico.nif = trabalha.nif
                WHERE
                    trabalha.nome = %(clinica)s; 
                """,
                {"clinica": clinica}
            )
            especialidades = cur.fetchall()
            log.debug(f"Found {cur.rowcount} rows.")

            if cur.rowcount == 0:
                return_msg = f"No specialties found in: {clinica}."
                return jsonify({"message": return_msg, "status": "error"}), 404

    return jsonify(especialidades), 200


#responsavel por listar todos os medicos de uma especialidade de uma clinica da base de dados saude
@app.route("/c/<clinica>/<especialidade>", methods=("GET",))
def list_doctors_from_speciality(clinica, especialidade):
    """Lists the name of all doctors from a specialty and the 3 next appointments"""

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM clinica
                WHERE nome = %(nome)s;
                """,
                {"nome": clinica}
            )
            
            if cur.rowcount == 0:
                return_msg = f"Clinic: {clinica} not found."
                return jsonify({"message": return_msg, "status": "error"}), 404

            doctors = cur.execute(
                """
                SELECT DISTINCT
                    medico.nome, medico.nif
                FROM 
                    medico
                JOIN 
                    horarios_disponiveis ON medico.nif = horarios_disponiveis.nif
                WHERE 
                    medico.especialidade = %(especialidade)s 
                    AND horarios_disponiveis.nome = %(clinica)s
                """,
                {"clinica": clinica, "especialidade": especialidade},
            ).fetchall()
            log.debug(f"Found {cur.rowcount} rows.")

            if cur.rowcount == 0:
                return_msg = f"No doctors found in: {clinica} with specialty: {especialidade}."
                return jsonify({"message": return_msg, "status": "error"}), 404

            resultado = []

            for medico in doctors:
                medico_nome, medico_nif = medico

                horarios = cur.execute(
                    """
                    SELECT 
                        data, hora
                    FROM 
                        horarios_disponiveis
                    WHERE 
                        data >= CURRENT_DATE
                        AND nome = %(clinica)s
                        AND nif = %(nif)s
                    ORDER BY data, hora
                    LIMIT 3;
                    """,
                    {"nif": medico_nif, "clinica": clinica},
                ).fetchall()
                log.debug(f"Found {cur.rowcount} rows.")

                horario_consulta= [(str(data), str(hora)) for data, hora in horarios]

                answer = {
                    "nome": medico_nome,
                    "horarios_disponiveis": horario_consulta,
                }
                resultado.append(answer)

    return jsonify(resultado), 200


#responsavel por registar uma consulta na base de dados saude
@app.route("/a/<clinica>/registar", methods=("POST",))
def regist_appointment(clinica):
    """Registers an appointment"""

    with pool.connection() as conn:
        with conn.cursor() as cur:

            cur.execute("SELECT MAX(id) FROM consulta;")
            max_id = cur.fetchone()[0]
            if max_id is None:
                max_id = 0

            cur.execute("SELECT MAX(codigo_sns) FROM consulta;")
            max_sns = cur.fetchone()[0]
            if max_sns is None:
                max_sns = 0

            consulta_id = int(max_id) + 1
            sns = int(max_sns) + 1

            cur.execute(
                """
                SELECT 1
                FROM clinica
                WHERE nome = %(nome)s;
                """,
                {"nome": clinica}
            )

            
            if cur.rowcount == 0:
                return_msg = f"Clinic: {clinica} not found."
                return jsonify({"message": return_msg, "status": "error"}), 404

            
            paciente = request.args.get("paciente")
            if not is_ssn(paciente):
                return jsonify({"message": "Invalid 'paciente' value.", "status": "error"}), 400
            
            cur.execute(
                """
                SELECT 1
                FROM paciente
                WHERE ssn = %(ssn)s;
                """,
                {"ssn": paciente}
            )
            if cur.rowcount == 0:
                return jsonify({"message": "paciente not found.", "status": "error"}), 400

            medico = request.args.get("medico")
            if not is_nif(medico):
                return jsonify({"message": "Invalid 'medico' value.", "status": "error"}), 400
            
            cur.execute(
                """
                SELECT 1
                FROM medico
                WHERE nif = %(nif)s;
                """,
                {"nif": medico}
            )
            if cur.rowcount == 0:
                return jsonify({"message": "medico not found.", "status": "error"}), 400
            
            data = request.args.get("data")
            if not is_data(data):
                return jsonify({"message": "Invalid 'data' value.", "status": "error"}), 400
            
            hora = request.args.get("hora")
            if not is_hora(hora):
                return jsonify({"message": "Invalid 'hora' value.", "status": "error"}), 400
            
            if not is_future_date_and_time(data, hora):
                return jsonify({"message": "Invalid date and time. Must be after the moment.", "status": "error"}), 400

            try:
                cur.execute(
                    """
                    INSERT INTO consulta (id, ssn, nif, nome, data, hora, codigo_sns)
                    VALUES (%(consulta_id)s, %(ssn)s, %(nif)s, %(clinica)s, %(data)s, %(hora)s, %(sns)s);
                    """,
                    {
                        "consulta_id": consulta_id,
                        "ssn": paciente,
                        "nif": medico,
                        "clinica": clinica,
                        "data": data,
                        "hora": hora,
                        "sns": sns
                    }
                )
                log.debug(f"Inserted {cur.rowcount} rows.")

            except Exception as e:

                if "Schedule not available" in str(e):
                    return jsonify({"message": "Schedule not available", "status": "error"}), 400
                
                return jsonify({"message": str(e), "status": "error"}), 500

    return jsonify({"message": "Appointment registered successfully.", "status": "success"}), 201


#responsavel por cancelar uma consulta na base de dados saude
@app.route("/a/<clinica>/cancelar", methods=("POST",))
def delete_appointment(clinica):
    """Deletes an appointment."""

    with pool.connection() as conn:
        with conn.cursor() as cur:
            
            cur.execute(
                """
                SELECT 1
                FROM clinica
                WHERE nome = %(nome)s;
                """,
                {"nome": clinica}
            )

            if cur.rowcount == 0:
                return_msg = f"Clinic: {clinica} not found."
                return jsonify({"message": return_msg, "status": "error"}), 404


            paciente = request.args.get("paciente")
            if not is_ssn(paciente):
                return jsonify({"message": "Invalid 'paciente' value.", "status": "error"}), 400

            cur.execute(
                """
                SELECT 1
                FROM paciente
                WHERE ssn = %(ssn)s;
                """,
                {"ssn": paciente}
            )
            if cur.rowcount == 0:
                return jsonify({"message": "paciente not found.", "status": "error"}), 400


            medico = request.args.get("medico")
            if not is_nif(medico):
                return jsonify({"message": "Invalid 'medico' value.", "status": "error"}), 400

            cur.execute(
                        """
                        SELECT 1
                        FROM medico
                        WHERE nif = %(nif)s;
                        """,
                        {"nif": medico}
                    )

            if cur.rowcount == 0:
                return jsonify({"message": "Médico not found.", "status": "error"}), 400

            data = request.args.get("data")
            if not is_data(data):
                return jsonify({"message": "Invalid 'data' value.", "status": "error"}), 400
            
            hora = request.args.get("hora")
            if not is_hora(hora):
                return jsonify({"message": "Invalid 'hora' value.", "status": "error"}), 400

            if not is_future_date_and_time(data, hora):
                return jsonify({"message": "Invalid date and time. Must be after the moment.", "status": "error"}), 400

            try:
                cur.execute(
                    """
                    DELETE FROM consulta
                    WHERE nome = %(clinica)s
                    AND ssn = %(ssn)s
                    AND nif = %(nif)s
                    AND data = %(data)s
                    AND hora = %(hora)s;
                    """,
                    {
                        "clinica": clinica,
                        "ssn": paciente,
                        "nif": medico,
                        "data": data,
                        "hora": hora
                    }
                )
                log.debug(f"Deleted {cur.rowcount} rows.")
                
                if cur.rowcount == 0:
                    return jsonify({"message": "Consulta not found.", "status": "error"}), 404
                            
            except Exception as e:

                if "Schedule not available" in str(e):
                    return jsonify({"message": "Schedule not available", "status": "error"}), 400
                
                return jsonify({"message": str(e), "status": "error"}), 500

    return jsonify({"message": "Appointment canceled successfully.", "status": "success"}), 200

@app.route("/ping", methods=("GET",))
def ping():
    log.debug("ping!")
    return jsonify({"message": "pong!", "status": "success"})


if __name__ == "__main__":
    app.run()