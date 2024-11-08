/** @odoo-module **/
import { Component, onWillStart, onMounted, markup, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class Database extends Component {
  setup() {
    this.state = useState({
      databases: this.props.action.params.databases,
    });
    this.notification = useService("notification");
    console.log(this);

    onMounted(() => {
      const footer = document.querySelector("footer");
      if (footer != null) footer.classList.add("d-none");
      const formSheet = document.querySelector(".modal-dialog");
      formSheet.setAttribute(
        "style",
        "max-width:600px; margin-left: auto; margin-right: auto;"
      );
      // Add iframe load event listener
      //get Database: type globalThis
      const self = this;
      const iframe = document.getElementById("hidden_frame");
      iframe.addEventListener("load", async () => {
        try {
          const iframeContent =
            iframe.contentDocument || iframe.contentWindow.document;
          const response = JSON.parse(iframeContent.body.textContent);
          if (response.status === "success") {
            // Close dialog and refresh view
            window.location.reload();
          } else if (response.message) {
            this.showNotification(response.message, "Error", "danger");
          }
        } catch (error) {}
      });
    });
  }

  showNotification(content, title, type) {
    const notification = this.notification;
    notification.add(content, {
      title: title,
      type: type,
      className: "p-4",
    });
  }
}

Database.template = "blogV2.database";
Database.props = { ...standardFieldProps };
registry.category("actions").add("blogV2.database", Database);
