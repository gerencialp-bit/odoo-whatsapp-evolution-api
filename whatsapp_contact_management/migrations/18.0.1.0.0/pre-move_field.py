# -*- coding: utf-8 -*-
import logging
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

def migrate(cr, version):
    """
    Moves the ownership of the 'whatsapp_instance_id' field on 'res.partner'
    from 'whatsapp_evolution_base' to 'whatsapp_contact_management'.
    This pre-migration script ensures that the database schema is updated
    correctly before the new module version is loaded, preventing data loss.
    """
    _logger.info("Starting migration to move 'whatsapp_instance_id' field from res.partner.")
    
    util.move_field_to_module(
        cr,
        model='res.partner',
        fieldname='whatsapp_instance_id',
        old_module='whatsapp_evolution_base',
        new_module='whatsapp_contact_management'
    )
    
    _logger.info("'whatsapp_instance_id' field successfully moved to 'whatsapp_contact_management'.")