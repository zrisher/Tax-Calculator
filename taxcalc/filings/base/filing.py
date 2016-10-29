import os
from taxcalc.utils import update_dict_ex
from taxcalc.filings.util import FormMapper


class Filing(FormMapper):
    """
    A collection of forms for a particular filer and year.
    """

    # Each filing should declare a recognized set of form classes
    FORM_CLASSES_BY_ID = None

    # and the rvar names to set given its own properties
    FILER_ID_RVAR = None
    FILING_YEAR_RVAR = None
    WEIGHT_RVAR = None

    @classmethod
    def fields_read(cls, year):
        """
        Get all fields used to generate rvars, indexed by form
        """
        results = {}
        for form_field_key in super(Filing, cls).fields_read(year):
            form_id, field_key = form_field_key.split('/')
            results[form_id] = results.get(form_id, set()) | {field_key}
        return results

    @classmethod
    def fields_written(cls, year):
        """
        Get all fields written from rvars, indexed by form
        """
        results = {}
        for form_field_key in super(Filing, cls).fields_written(year):
            form_id, field_key = form_field_key.split('/')
            results[form_id] = results.get(form_id, set()) | {field_key}
        return results

    @classmethod
    def rvars_generated(cls, year):
        """
        Extend FormMapper's list with the rvars we generate automatically
        """
        results = super(Filing, cls).rvars_generated(year)
        results.update({
            cls.FILER_ID_RVAR, cls.FILING_YEAR_RVAR, cls.WEIGHT_RVAR
        })
        return results

    @classmethod
    def fields_read_with_forms(cls, year):
        """
        Return the fields read by the filing and its forms, indexed by form
        """
        results = {}
        for form_id, form_class in cls.FORM_CLASSES_BY_ID.items():
            results[form_id] = form_class.fields_read(year)
        for form_id, fields in cls.fields_read(year).items():
            results[form_id].update(fields)
        return results

    @classmethod
    def fields_written_with_forms(cls, year):
        """
        Return the fields written by the filing and its forms, indexed by form
        """
        results = {}
        for form_id, form_class in cls.FORM_CLASSES_BY_ID.items():
            results[form_id] = form_class.fields_written(year)
        for form_id, fields in cls.fields_written(year).items():
            results[form_id].update(fields)
        return results

    @classmethod
    def rvars_generated_with_forms(cls, year):
        """
        Return the rvars generated by the filing and its forms, indexed by form
        """
        results = cls.rvars_generated(year)
        for form_class in cls.FORM_CLASSES_BY_ID.values():
            results.update(form_class.rvars_generated(year))
        return results

    @classmethod
    def rvars_used_with_forms(cls, year):
        """
        Return the rvars used by the filing and its forms, indexed by form
        """
        results = cls.rvars_used(year)
        for form_class in cls.FORM_CLASSES_BY_ID.values():
            results.update(form_class.rvars_used(year))
        return results

    @classmethod
    def example(cls, year, filer_id='0',
                all_inputs=False, all_valid=False, drop_empty=False):
        """
        Create an example filing for year filled with example form_classes.
        """
        filing = cls(year, filer_id)
        for form_class in cls.FORM_CLASSES_BY_ID.values():
            filing.add_form(form_class.example(
                year,
                all_inputs=all_inputs, all_valid=all_valid, filer_id=filer_id
            ))
        if all_inputs:
            filing.fill_inputs()
        if drop_empty:
            filing.drop_empty_forms()
        return filing

    def __init__(self, year, filer_id):
        """
        Construct a Filing.
        """
        super(Filing, self).__init__(year)
        self._forms = {}
        self._filer_id = filer_id
        self._year = year

    @property
    def year(self):
        """
        Filing year. Same for all contained forms.
        """
        return self._year

    @property
    def filer_id(self):
        """
        Filer id. Same for all contained forms.
        """
        return self._filer_id

    @property
    def forms(self):
        """
        Filer id. Same for all contained forms.
        """
        return self._forms.copy()

    def add_form(self, form):
        """
        Adds a new form to the filing.
        Errors if the filer/year don't match or if already exists.
        """
        if form.filer_id != self.filer_id:
            raise ValueError("Supplied form is for a different tax filer.")
        if form.year != self.year:
            raise ValueError("Supplied form is for a different year.")
        update_dict_ex(self._forms, form.form_id(), form)

    def drop_empty_forms(self):
        """
        Remove all empty forms from the filing.
        """
        for form_id in list(self._forms.keys()):
            if self._forms[form_id].is_empty:
                del self._forms[form_id]

    def fill_inputs(self):
        """
        Fill all input_fields from the filing's read map.
        """
        for form_id, fields in self.fields_read(self.year).items():
            if form_id in self._forms:
                for field in fields:
                    self._forms[form_id].set_field(field, '0')

    def to_dir(self, path):
        """
        Writes all forms to path as format.
        """
        os.makedirs(path, exist_ok=True)
        for form_id, form in self._forms.items():
            form.to_json_file(os.path.join(path, form_id + '.json'))

    def _read_store(self):
        """
        Aggregate form field data with composite keys for FormMapper
        """
        result = {}
        return {
            form_id + '/' + field_key: value
            for form_id, form in self._forms.items()
            for field_key, value in form.fields.items()
        }

    def _write_store(self, data):
        """
        Parse composite-keyed values and write data back to forms
        """
        for form_field_key, value in data.items():
            form_id, field_key = form_field_key.split('/')
            self._forms[form_id].set_field(field_key, value)

    def read_rvars(self):
        results = super(Filing, self).read_rvars()
        results.update({
            self.FILER_ID_RVAR: str(self.filer_id),
            self.FILING_YEAR_RVAR: str(self.year),
            self.WEIGHT_RVAR: '1'
        })
        return results

    def read_rvars_with_forms(self):
        """
        Collect all rvars from forms, then add own map output.
        """
        results = self.read_rvars()
        for form in self._forms.values():
            results.update(form.read_rvars())
        return results

    def ensure_written_forms_available(self):
        """
        Create any forms that don't exist but can be written from rvars
        """
        for form_id in self.fields_written_with_forms(self.year):
            if form_id not in self._forms:
                form_class = self.FORM_CLASSES_BY_ID[form_id]
                new_form = form_class(self.year, filer_id=self.filer_id)
                self.add_form(new_form)

    def write_rvars_with_forms(self, data):
        """
        Write to both form mappings and own interform mapping
        """
        self.ensure_written_forms_available()
        self.write_rvars(data)
        for form in self._forms.values():
            form.write_rvars(data)