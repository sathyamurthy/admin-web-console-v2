var Cell = Datagrid.Cell = Backbone.View.extend({
  tagName: 'td',

  initialize: function(options) {
    this.options = options;
    this.column  = this.options.column;
  },

  render: function() {
    this._prepareValue();
    this.$el.html(this.value);
    return this;
  },

  _prepareValue: function() {
    this.value = this.model.get(this.column.property);
  }
});
