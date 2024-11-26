from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import pytz
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class BlogTransferScheduler(models.Model):
    _name = 'blog.transfer.scheduler'
    _description = 'Blog Transfer Scheduler'

    name = fields.Char(string='Tên Chiến Dịch', required=True)
    blog_transfer_id = fields.Many2one(
        'blog.transfer',
        string='Chiến dịch chuyển',
    )

    @api.model
    def _run_transfer_jobs(self):
        """Phương thức được gọi bởi cron job để thực hiện các chiến dịch chuyển"""

        current_time = fields.Datetime.now()
        schedulers = self.search([])

        for scheduler in schedulers:
            try:
                if scheduler.blog_transfer_id.scheduled_date <= current_time:
                    scheduler.blog_transfer_id.action_start_transfer()
            except Exception as e:
                _logger.error(
                    f"Error processing transfer: {str(e)}")
                continue
