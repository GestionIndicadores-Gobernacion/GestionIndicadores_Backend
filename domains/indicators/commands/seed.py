import click
from flask.cli import with_appcontext

from domains.indicators.handlers.strategy_handler import StrategyHandler
from domains.indicators.handlers.component_handler import ComponentHandler
from domains.indicators.models.Strategy.strategy import Strategy

from .seed_data import STRATEGIES, indicator


@click.command("seed")
@with_appcontext
def seed():

    click.echo("\n🌱 Cargando estrategias masivas...\n")

    for strategy_data in STRATEGIES:

        existing = Strategy.query.filter_by(name=strategy_data["name"]).first()
        if existing:
            click.echo(f"• {strategy_data['name']} ya existe")
            continue

        # -------- crear estrategia ----------
        strategy_payload = {
            "name": strategy_data["name"],
            "objective": strategy_data["objective"],
            "product_goal_description": strategy_data["product_goal_description"],
            "annual_goals": strategy_data["annual_goals"]
        }

        strategy, errors = StrategyHandler.create(strategy_payload)

        if errors:
            click.echo(f"Error creando estrategia: {strategy_data['name']}")
            continue

        click.echo(f"\n✔ Estrategia creada: {strategy.name}")

        # -------- componentes ----------
        for comp in strategy_data["components"]:

            data = {
                "strategy_id": strategy.id,
                "name": comp["name"],
                "objectives": [{"description": o} for o in comp["objectives"]],
                "mga_activities": [{"name": m} for m in comp["mga"]],
                "indicators": [indicator()]
            }

            component, errors = ComponentHandler.create(data)

            if errors:
                click.echo(f"   ✖ {comp['name']}")
            else:
                click.echo(f"   └─ {comp['name']}")

    click.echo("\nSeed finalizado.")
