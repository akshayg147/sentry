import {useCallback} from 'react';
import styled from '@emotion/styled';

import {SegmentedControl} from 'sentry/components/segmentedControl';
import {t} from 'sentry/locale';

interface DifferentialFlamegraphNegationSwitchProps {
  negated: boolean;
  onNegatedChange: (negated: boolean) => void;
}
export function DifferentialFlamegraphNegationSwitch(
  props: DifferentialFlamegraphNegationSwitchProps
) {
  const onNegatedChange = props.onNegatedChange;
  const onWrapChange = useCallback(
    (value: 'negated' | 'regular') => {
      onNegatedChange(value === 'negated');
    },
    [onNegatedChange]
  );

  return (
    <DifferentialFlamegraphNegationSwitchContainer>
      <SegmentedControl
        aria-label={t('View')}
        size="xs"
        value={props.negated ? 'negated' : 'regular'}
        onChange={onWrapChange}
      >
        <SegmentedControl.Item key="negated">{t('Before → After')}</SegmentedControl.Item>
        <SegmentedControl.Item key="regular">{t('After → Before')}</SegmentedControl.Item>
      </SegmentedControl>
    </DifferentialFlamegraphNegationSwitchContainer>
  );
}

const DifferentialFlamegraphNegationSwitchContainer = styled('div')`
  /* after this size, the text is quickly truncated */
  min-width: 210px;
`;
