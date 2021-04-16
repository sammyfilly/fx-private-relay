from datetime import datetime, timedelta, timezone
from hashlib import sha256
import random
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase

from allauth.socialaccount.models import SocialAccount

from model_bakery import baker

from ..models import (
    CannotMakeAddressException,
    DeletedAddress,
    DomainAddress,
    RelayAddress,
    Profile
)


class RelayAddressTest(TestCase):
    def setUp(self):
        self.user = baker.make(User)

    def test_make_relay_address_assigns_to_user(self):
        relay_address = RelayAddress.make_relay_address(self.user)
        assert relay_address.user == self.user

    def test_make_relay_address_makes_different_addresses(self):
        for i in range(1000):
            RelayAddress.make_relay_address(self.user)
        # check that the address is unique (deeper assertion that the generated aliases are unique)
        relay_addresses = RelayAddress.objects.filter(user=self.user).values_list("address", flat=True)
        assert len(relay_addresses) == 1000

    def test_delete_adds_deleted_address_object(self):
        relay_address = baker.make(RelayAddress)
        address_hash = sha256(
            relay_address.address.encode('utf-8')
        ).hexdigest()
        relay_address.delete()
        deleted_count = DeletedAddress.objects.filter(
            address_hash=address_hash
        ).count()
        assert deleted_count == 1

    # trigger a collision by making address_default always return 'aaaaaaaaa'
    @patch.multiple('string', ascii_lowercase='a', digits='')
    def test_make_relay_address_doesnt_make_dupe_of_deleted(self):
        test_hash = sha256('aaaaaaaaa'.encode('utf-8')).hexdigest()
        DeletedAddress.objects.create(address_hash=test_hash)
        try:
            RelayAddress.make_relay_address(self.user)
        except CannotMakeAddressException:
            return
        self.fail("Should have raise CannotMakeAddressException")


class ProfileTest(TestCase):
    def setUp(self):
        self.profile = baker.make(Profile)

    def test_bounce_paused_no_bounces(self):
        bounce_paused, bounce_type = self.profile.check_bounce_pause()

        assert bounce_paused == False
        assert bounce_type == ''

    def test_bounce_paused_hard_bounce_pending(self):
        self.profile.last_hard_bounce = (
            datetime.now(timezone.utc) -
            timedelta(days=settings.HARD_BOUNCE_ALLOWED_DAYS-1)
        )
        self.profile.save()

        bounce_paused, bounce_type = self.profile.check_bounce_pause()

        assert bounce_paused == True
        assert bounce_type == 'hard'

    def test_bounce_paused_soft_bounce_pending(self):
        self.profile.last_soft_bounce = (
            datetime.now(timezone.utc) -
            timedelta(days=settings.SOFT_BOUNCE_ALLOWED_DAYS-1)
        )
        self.profile.save()

        bounce_paused, bounce_type = self.profile.check_bounce_pause()

        assert bounce_paused == True
        assert bounce_type == 'soft'

    def test_bounce_paused_hardd_and_soft_bounce_pending_shows_hard(self):
        self.profile.last_hard_bounce = (
            datetime.now(timezone.utc) -
            timedelta(days=settings.HARD_BOUNCE_ALLOWED_DAYS-1)
        )
        self.profile.last_soft_bounce = (
            datetime.now(timezone.utc) -
            timedelta(days=settings.SOFT_BOUNCE_ALLOWED_DAYS-1)
        )
        self.profile.save()
        bounce_paused, bounce_type = self.profile.check_bounce_pause()

        assert bounce_paused == True
        assert bounce_type == 'hard'

    def test_bounce_paused_hard_bounce_over_resets_timer(self):
        self.profile.last_hard_bounce = (
            datetime.now(timezone.utc) -
            timedelta(days=settings.HARD_BOUNCE_ALLOWED_DAYS+1)
        )
        self.profile.save()

        assert self.profile.last_hard_bounce is not None

        bounce_paused, bounce_type = self.profile.check_bounce_pause()

        assert bounce_paused == False
        assert bounce_type == ''
        assert self.profile.last_hard_bounce == None

    def test_bounce_paused_soft_bounce_over_resets_timer(self):
        self.profile.last_soft_bounce = (
            datetime.now(timezone.utc) -
            timedelta(days=settings.SOFT_BOUNCE_ALLOWED_DAYS+1)
        )
        self.profile.save()

        assert self.profile.last_soft_bounce is not None

        bounce_paused, bounce_type = self.profile.check_bounce_pause()

        assert bounce_paused == False
        assert bounce_type == ''
        assert self.profile.last_soft_bounce == None

    def test_next_email_try_no_bounces_returns_today(self):
        assert (
            self.profile.next_email_try.date() ==
            datetime.now(timezone.utc).date()
        )

    def test_next_email_try_hard_bounce_returns_proper_datemath(self):
        last_hard_bounce = (
            datetime.now(timezone.utc) -
            timedelta(days=settings.HARD_BOUNCE_ALLOWED_DAYS-1)
        )
        self.profile.last_hard_bounce = last_hard_bounce
        self.profile.save()

        expected_next_try_date = last_hard_bounce + timedelta(
            days=settings.HARD_BOUNCE_ALLOWED_DAYS
        )
        assert (
            self.profile.next_email_try.date() == expected_next_try_date.date()
        )

    def test_next_email_try_soft_bounce_returns_proper_datemath(self):
        last_soft_bounce = (
            datetime.now(timezone.utc) -
            timedelta(days=settings.SOFT_BOUNCE_ALLOWED_DAYS-1)
        )
        self.profile.last_soft_bounce = last_soft_bounce
        self.profile.save()

        expected_next_try_date = last_soft_bounce + timedelta(
            days=settings.SOFT_BOUNCE_ALLOWED_DAYS
        )
        assert (
            self.profile.next_email_try.date() == expected_next_try_date.date()
        )

    def test_next_email_try_hard_and_soft_bounce_returns_hard_datemath(self):
        last_soft_bounce = (
            datetime.now(timezone.utc) -
            timedelta(days=settings.SOFT_BOUNCE_ALLOWED_DAYS-1)
        )
        self.profile.last_soft_bounce = last_soft_bounce
        last_hard_bounce = (
            datetime.now(timezone.utc) -
            timedelta(days=settings.HARD_BOUNCE_ALLOWED_DAYS-1)
        )
        self.profile.last_hard_bounce = last_hard_bounce
        self.profile.save()

        expected_next_try_date = last_hard_bounce + timedelta(
            days=settings.HARD_BOUNCE_ALLOWED_DAYS
        )
        assert (
            self.profile.next_email_try.date() == expected_next_try_date.date()
        )

    def test_last_bounce_date_no_bounces_returns_None(self):
        assert self.profile.last_bounce_date == None

    def test_last_bounce_date_soft_bounce_returns_its_date(self):
        last_soft_bounce = (
            datetime.now(timezone.utc) -
            timedelta(days=settings.SOFT_BOUNCE_ALLOWED_DAYS-1)
        )
        self.profile.last_soft_bounce = last_soft_bounce
        self.profile.save()

        assert self.profile.last_bounce_date == self.profile.last_soft_bounce

    def test_last_bounce_date_hard_bounce_returns_its_date(self):
        last_hard_bounce = (
            datetime.now(timezone.utc) -
            timedelta(days=settings.HARD_BOUNCE_ALLOWED_DAYS-1)
        )
        self.profile.last_hard_bounce = last_hard_bounce
        self.profile.save()

        assert self.profile.last_bounce_date == self.profile.last_hard_bounce

    def test_last_bounce_date_hard_and_soft_bounces_returns_hard_date(self):
        last_soft_bounce = (
            datetime.now(timezone.utc) -
            timedelta(days=settings.SOFT_BOUNCE_ALLOWED_DAYS-1)
        )
        self.profile.last_soft_bounce = last_soft_bounce
        last_hard_bounce = (
            datetime.now(timezone.utc) -
            timedelta(days=settings.HARD_BOUNCE_ALLOWED_DAYS-1)
        )
        self.profile.last_hard_bounce = last_hard_bounce
        self.profile.save()

        assert self.profile.last_bounce_date == self.profile.last_hard_bounce

    def test_has_unlimited_default_False(self):
        assert self.profile.has_unlimited == False

    def test_has_unlimited_with_unlimited_subsription_returns_True(self):
        premium_user = baker.make(User)
        random_sub = random.choice(
            settings.SUBSCRIPTIONS_WITH_UNLIMITED.split(',')
        )
        socialaccount = baker.make(
            SocialAccount,
            user=premium_user,
            provider='fxa',
            extra_data={'subscriptions': [random_sub]}
        )
        premium_profile = baker.make(Profile, user=premium_user)
        assert premium_profile.has_unlimited == True
