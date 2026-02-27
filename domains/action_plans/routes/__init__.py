from domains.action_plans.routes.action_plan_routes import blp as action_plans_blp

def register_routes(api):
    api.register_blueprint(action_plans_blp)