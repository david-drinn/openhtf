# Copyright 2016 Google Inc. All Rights Reserved.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest

import attr
import mock

import openhtf
from openhtf import plugs
from openhtf.core import base_plugs


def plain_func():
  """Plain Docstring."""
  pass


def normal_test_phase():
  return 'return value'


@openhtf.PhaseOptions(name='func-name({input_value[0]})')
def extra_arg_func(input_value=None):
  return input_value


class ExtraPlug(base_plugs.BasePlug):
  name = 'extra_plug_0'

  def echo(self, phrase):
    return '%s says %s' % (self.name, phrase)


@openhtf.PhaseOptions(name='extra_plug_func[{plug.name}][{phrase}]')
@plugs.plug(plug=ExtraPlug.placeholder)
def extra_plug_func(plug, phrase):
  return plug.echo(phrase)


class PlaceholderCapablePlug(base_plugs.BasePlug):
  auto_placeholder = True


class SubPlaceholderCapablePlug(PlaceholderCapablePlug):
  pass


@plugs.plug(placed=PlaceholderCapablePlug)
def placeholder_using_plug(placed):
  del placed  # Unused.


@plugs.plug(subplaced=SubPlaceholderCapablePlug)
def sub_placeholder_using_plug(subplaced):
  del subplaced  # Unused.


class NonPlugBase(object):
  """A base class that is not a BasePlug."""


class PlugVersionOfNonPlug(NonPlugBase, base_plugs.BasePlug):
  """Plug implementation of a non-plug base."""


custom_placeholder = base_plugs.PlugPlaceholder(NonPlugBase)


@plugs.plug(custom=custom_placeholder)
def custom_placeholder_phase(custom):
  del custom  # Unused.


class TestPhaseDescriptor(unittest.TestCase):

  def setUp(self):
    super(TestPhaseDescriptor, self).setUp()
    self._phase_data = mock.Mock(
        plug_manager=plugs.PlugManager(), execution_uid='01234567890')

  def test_basics(self):
    phase = openhtf.PhaseDescriptor.wrap_or_copy(plain_func)
    self.assertIs(phase.func, plain_func)  # pytype: disable=wrong-arg-types
    self.assertEqual(0, len(phase.plugs))
    self.assertEqual('plain_func', phase.name)
    self.assertEqual('Plain Docstring.', phase.doc)
    phase(self._phase_data)

    test_phase = openhtf.PhaseDescriptor.wrap_or_copy(normal_test_phase)
    self.assertEqual('normal_test_phase', test_phase.name)
    self.assertEqual('return value', test_phase(self._phase_data))

  def test_multiple_phases(self):
    phase = openhtf.PhaseDescriptor.wrap_or_copy(plain_func)
    second_phase = openhtf.PhaseDescriptor.wrap_or_copy(phase)
    for field in attr.fields(type(phase)):
      if field.name == 'func':
        continue
      self.assertIsNot(
          getattr(phase, field.name), getattr(second_phase, field.name))

  def test_callable_name_with_args(self):

    def namer(**kwargs):
      return 'renamed_{one}_{two}'.format(**kwargs)

    @openhtf.PhaseOptions(name=namer)
    def custom_phase(one=None, two=None):
      del one  # Unused.
      del two  # Unused.

    self.assertEqual('custom_phase', custom_phase.name)
    arged = custom_phase.with_args(one=1, two=2)
    self.assertEqual('renamed_1_2', arged.name)

  def test_with_args(self):
    phase = extra_arg_func.with_args(input_value='input arg')
    result = phase(self._phase_data)
    first_result = phase(self._phase_data)
    self.assertIs(phase.func, extra_arg_func.func)
    self.assertEqual('input arg', result)
    self.assertEqual('func-name(i)', phase.name)
    self.assertEqual('input arg', first_result)

    # Must do with_args() on the original phase, otherwise it has already been
    # formatted and the format-arg information is lost.
    second_phase = extra_arg_func.with_args(input_value='second input')
    second_result = second_phase(self._phase_data)
    self.assertEqual('second input', second_result)
    self.assertEqual('func-name(s)', second_phase.name)

  def test_with_args_argument_not_specified(self):
    phase = extra_arg_func.with_args(arg_does_not_exist=1)
    self.assertNotIn('arg_does_not_exist', phase.extra_kwargs)

  def test_with_args_kwargs(self):
    @openhtf.PhaseOptions()
    def phase(test_api, **kwargs):
      del test_api  # Unused.
      del kwargs  # Unused.

    updated = phase.with_args(arg_does_not_exist=1)
    self.assertEqual({'arg_does_not_exist': 1}, updated.extra_kwargs)

  def test_with_plugs(self):
    self._phase_data.plug_manager.initialize_plugs([ExtraPlug])
    phase = extra_plug_func.with_plugs(plug=ExtraPlug).with_args(phrase='hello')
    self.assertIs(phase.func, extra_plug_func.func)
    self.assertEqual(1, len(phase.plugs))
    self.assertEqual('extra_plug_func[extra_plug_0][hello]', phase.options.name)
    self.assertEqual('extra_plug_func[extra_plug_0][hello]', phase.name)

    result = phase(self._phase_data)
    self.assertEqual('extra_plug_0 says hello', result)

  def test_with_plugs_unknown_plug_name_ignored(self):
    phase = placeholder_using_plug.with_plugs(undefined_plug=ExtraPlug)
    self.assertIs(phase, placeholder_using_plug)

  def test_with_plugs_auto_placeholder(self):
    phase = placeholder_using_plug.with_plugs(placed=SubPlaceholderCapablePlug)
    self.assertIs(phase.func, placeholder_using_plug.func)
    self.assertEqual(1, len(phase.plugs))

  def test_with_plugs_subclass_auto_placeholder_error(self):
    with self.assertRaises(base_plugs.InvalidPlugError):
      sub_placeholder_using_plug.with_plugs(subplaced=SubPlaceholderCapablePlug)

  def test_with_plugs_auto_placeholder_non_subclass_error(self):
    with self.assertRaises(base_plugs.InvalidPlugError):
      placeholder_using_plug.with_plugs(placed=ExtraPlug)

  def test_with_plugs_custom_placeholder_is_base_plug(self):
    phase = custom_placeholder_phase.with_plugs(custom=PlugVersionOfNonPlug)
    self.assertIs(phase.func, custom_placeholder_phase.func)
    self.assertEqual([base_plugs.PhasePlug('custom', PlugVersionOfNonPlug)],
                     phase.plugs)
