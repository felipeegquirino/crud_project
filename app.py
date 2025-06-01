from flask import Flask, render_template, url_for, request, redirect, flash, send_file
from flask_mysqldb import MySQL

app = Flask(__name__)

app.config["MYSQL_HOST"] = "localhost"
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = "ad12345678910"
app.config["MYSQL_DB"] = "crud_db"
app.config["SECRET_KEY"] = "sua_chave_secreta"

mysql = MySQL(app)


@app.route("/")
def index():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT items.id, items.nome, items.categoria, items.quantidade, items.preco, items.localizacao, localizacoes.deposito, localizacoes.prateleira 
        FROM items 
        LEFT JOIN localizacoes ON items.id = localizacoes.item_id
    """)
    items = cur.fetchall()
    return render_template("index.html", items=items)



@app.route("/add", methods=["POST"])
def adicionar_item():
    if request.method == "POST":
        nome = request.form["nome"]
        categoria = request.form["categoria"]
        quantidade = request.form["quantidade"]
        preco = request.form["preco"]
        localizacao = request.form["localizacao"]
        deposito = request.form["deposito"]
        prateleira = request.form["prateleira"]

        try:
            cur = mysql.connection.cursor()
            cur.execute(
                "INSERT INTO items (nome, categoria, quantidade, preco, localizacao) VALUES (%s, %s, %s, %s, %s)",
                (nome, categoria, quantidade, preco, localizacao),
            )
            cur.execute(
                "INSERT INTO localizacoes (item_id, deposito, prateleira) VALUES (LAST_INSERT_ID(), %s, %s)",
                (deposito, prateleira),
            )
            mysql.connection.commit()

            
            registrar_movimentacao(nome, categoria, quantidade, "entrada")

            flash("Item adicionado com sucesso!", "success")
        except:
            flash("Erro ao adicionar item.", "danger")
        return redirect(url_for("index"))


@app.route("/edit/<int:id>", methods=["GET", "POST"])
def editar_item(id):
    cur = mysql.connection.cursor()
    if request.method == "POST":
        nome = request.form["nome"]
        categoria = request.form["categoria"]
        quantidade = request.form["quantidade"]
        preco = request.form["preco"]
        localizacao = request.form["localizacao"]
        deposito = request.form["deposito"]
        prateleira = request.form["prateleira"]
        try:
            cur.execute(
                "UPDATE items SET nome=%s, categoria=%s, quantidade=%s, preco=%s, localizacao=%s WHERE id=%s",
                (nome, categoria, quantidade, preco, localizacao, id),
            )
            cur.execute(
                "INSERT INTO localizacoes (item_id, deposito, prateleira) VALUES (%s, %s, %s) "
                "ON DUPLICATE KEY UPDATE deposito=%s, prateleira=%s",
                (id, deposito, prateleira, deposito, prateleira),
            )
            mysql.connection.commit()
            flash("Item editado com sucesso!", "success")
        except:
            flash("Erro ao editar item.", "danger")
        return redirect(url_for("index"))

    cur.execute("""
        SELECT items.*, localizacoes.deposito, localizacoes.prateleira
        FROM items
        LEFT JOIN localizacoes ON items.id = localizacoes.item_id
        WHERE items.id = %s
    """, (id,))
    item = cur.fetchone()
    return render_template("edit.html", item=item)



@app.route("/localizacao")
def listar_localizacao():
    cur = mysql.connection.cursor()
    cur.execute(
        "SELECT items.nome, localizacoes.deposito, localizacoes.prateleira FROM localizacoes "
        "JOIN items ON items.id = localizacoes.item_id"
    )
    localizacao = cur.fetchall()
    return render_template("localizacao.html", localizacao=localizacao)


@app.route("/delete/<int:id>")
def deletar_item(id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM localizacoes WHERE item_id=%s", (id,))

        
        cur.execute("SELECT nome, categoria, quantidade FROM items WHERE id=%s", (id,))
        item = cur.fetchone()

        cur.execute("DELETE FROM items WHERE id=%s", (id,))
        mysql.connection.commit()

        
        registrar_movimentacao(item[0], item[1], item[2], "saida")

        flash("Item deletado com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao deletar item: {e}", "danger")
    finally:
        cur.close()
    return redirect(url_for("index"))


@app.route("/report")
def gerar_relatorio():
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT items.id, items.nome, items.categoria, items.quantidade, items.preco, items.localizacao, localizacoes.deposito, localizacoes.prateleira 
        FROM items 
        LEFT JOIN localizacoes ON items.id = localizacoes.item_id 
        WHERE items.quantidade < %s
    """, (10,))
    estoque_baixo = cur.fetchall()

    cur.execute("""
        SELECT items.id, items.nome, items.categoria, items.quantidade, items.preco, items.localizacao, localizacoes.deposito, localizacoes.prateleira 
        FROM items 
        LEFT JOIN localizacoes ON items.id = localizacoes.item_id 
        WHERE items.quantidade > %s
    """, (100,))
    excesso_estoque = cur.fetchall()

    cur.execute("SELECT * FROM movimentacoes")
    movimentacoes = cur.fetchall()

    with open("relatorio_estoque.csv", "w") as f:
        f.write("Relatório de Estoque Baixo\n")
        f.write("ID, Nome, Categoria, Quantidade, Preço, Localização\n")
        for item in estoque_baixo:
            f.write(
                f"{item[0]}, {item[1]}, {item[2]}, {item[3]}, {item[4]}, {item[5]}\n"
            )

        f.write("\nRelatório de Excesso de Estoque\n")
        f.write("ID, Nome, Categoria, Quantidade, Preço, Localização\n")
        for item in excesso_estoque:
            f.write(
                f"{item[0]}, {item[1]}, {item[2]}, {item[3]}, {item[4]}, {item[5]}\n"
            )

        f.write("\nRelatório de Movimentações\n")
        f.write("ID do Item, Tipo, Nome, Categoria, Quantidade, Data\n")
        for mov in movimentacoes:
            f.write(f"{mov[0]}, {mov[1]}, {mov[2]}, {mov[3]}, {mov[4]}, {mov[5]}\n")

    return "Relatório gerado com sucesso! Você pode baixar o arquivo <a href='/download_report'>aqui</a>."


@app.route("/download_report")
def download_report():
    return send_file("relatorio_estoque.csv", as_attachment=True)


def registrar_movimentacao(nome, categoria, quantidade, tipo):
    cur = mysql.connection.cursor()
    try:
        cur.execute(
            "INSERT INTO movimentacoes (item_id, tipo, quantidade, nome, categoria) VALUES ((SELECT id FROM items WHERE nome = %s), %s, %s, %s, %s)",
            (nome, tipo, quantidade, nome, categoria),
        )
        mysql.connection.commit()
    except Exception as e:
        print(f"Erro ao registrar movimentação: {e}")
    finally:
        cur.close()


@app.route("/relatorio_movimentacoes")
def relatorio_movimentacoes():
    cur = mysql.connection.cursor()
    cur.execute(
        "SELECT item_id, tipo, nome, categoria, quantidade, data FROM movimentacoes"
    )
    movimentacoes = cur.fetchall()

    report = "ID do Item, Tipo, Nome, Categoria, Quantidade, Data\n"
    for mov in movimentacoes:
        report += f"{mov[0]}, {mov[1]}, {mov[2]}, {mov[3]}, {mov[4]}, {mov[5]}\n"

    with open("movimentacoes_report.csv", "w") as f:
        f.write(report)

    return "Relatório de movimentações gerado com sucesso! Você pode baixar o arquivo <a href='/download_movimentacoes_report'>aqui</a>."


@app.route("/download_movimentacoes_report")
def download_movimentacoes_report():
    return send_file("movimentacoes_report.csv", as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
