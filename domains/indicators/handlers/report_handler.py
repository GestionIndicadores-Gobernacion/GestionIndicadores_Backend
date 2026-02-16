from extensions import db
from domains.indicators.models.Report.report import Report, ZoneTypeEnum
from domains.indicators.models.Report.report_indicator_value import ReportIndicatorValue
from domains.indicators.validators.report_validator import ReportValidator


class ReportHandler:

    @staticmethod
    def create(data):

        errors = ReportValidator.validate_create(data)
        if errors:
            return None, errors

        try:
            report = Report(
                strategy_id=data["strategy_id"],
                component_id=data["component_id"],
                report_date=data["report_date"],
                executive_summary=data["executive_summary"],
                activities_performed=data["activities_performed"],
                intervention_location=data["intervention_location"],
                zone_type=ZoneTypeEnum(data["zone_type"]),
                evidence_link=data.get("evidence_link")
            )

            db.session.add(report)
            db.session.flush()

            for val in data["indicator_values"]:
                db.session.add(
                    ReportIndicatorValue(
                        report_id=report.id,
                        indicator_id=val["indicator_id"],
                        value=val["value"]
                    )
                )

            db.session.commit()
            return report, None

        except Exception as e:
            db.session.rollback()
            return None, {"database": str(e)}

    @staticmethod
    def update(report, data):

        errors = ReportValidator.validate_create(data)
        if errors:
            return None, errors

        try:
            report.strategy_id = data["strategy_id"]
            report.component_id = data["component_id"]
            report.report_date = data["report_date"]
            report.executive_summary = data["executive_summary"]
            report.activities_performed = data["activities_performed"]
            report.intervention_location = data["intervention_location"]
            report.zone_type = ZoneTypeEnum(data["zone_type"])
            report.evidence_link = data.get("evidence_link")

            # eliminar correctamente usando relación
            report.indicator_values.clear()
            db.session.flush()

            for val in data["indicator_values"]:
                report.indicator_values.append(
                    ReportIndicatorValue(
                        indicator_id=val["indicator_id"],
                        value=val["value"]
                    )
                )

            db.session.commit()
            return report, None

        except Exception as e:
            db.session.rollback()
            return None, {"database": str(e)}

    @staticmethod
    def get_all():
        return Report.query.order_by(Report.report_date.desc()).all()

    @staticmethod
    def get_by_id(report_id):
        return Report.query.get(report_id)

    @staticmethod
    def delete(report):
        db.session.delete(report)
        db.session.commit()
