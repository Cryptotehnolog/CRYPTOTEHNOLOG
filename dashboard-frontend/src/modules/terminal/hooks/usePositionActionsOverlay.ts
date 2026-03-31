import { type MouseEvent as ReactMouseEvent, useEffect, useRef, useState } from "react";

export type PositionActionPending<TAction extends string> = {
  rowKey: string;
  action: TAction;
} | null;

type OverlayPoint = {
  top: number;
  left: number;
};

type OverlaySize = {
  width: number;
  height: number;
};

type UsePositionActionsOverlayOptions = {
  hasRowKey: (rowKey: string) => boolean;
  menuEstimate: OverlaySize;
  confirmEstimate: OverlaySize;
};

export function usePositionActionsOverlay<TAction extends string>(
  options: UsePositionActionsOverlayOptions,
) {
  const [openPositionActionsFor, setOpenPositionActionsFor] = useState<string | null>(null);
  const [pendingPositionAction, setPendingPositionAction] =
    useState<PositionActionPending<TAction>>(null);
  const [positionActionOverlayPosition, setPositionActionOverlayPosition] =
    useState<OverlayPoint | null>(null);
  const positionActionsLayerRef = useRef<HTMLDivElement | null>(null);
  const positionActionAnchorRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const clearPositionActions = () => {
    setOpenPositionActionsFor(null);
    setPendingPositionAction(null);
    setPositionActionOverlayPosition(null);
  };

  const resolvePositionActionPlacement = (
    rowKey: string,
    layerSize?: OverlaySize,
    anchorElement?: HTMLElement | null,
  ) => {
    const anchor = anchorElement ?? positionActionAnchorRefs.current[rowKey];

    if (!anchor) {
      setPositionActionOverlayPosition(null);
      return;
    }

    const overlayGap = 6;
    const safeX = 12;
    const safeY = 10;
    const anchorRect = anchor.getBoundingClientRect();
    const layerWidth = layerSize?.width ?? options.menuEstimate.width;
    const layerHeight = layerSize?.height ?? options.menuEstimate.height;
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const anchorTop = Math.min(
      Math.max(anchorRect.top, safeY),
      viewportHeight - safeY - anchorRect.height,
    );
    const anchorBottom = anchorTop + anchorRect.height;
    const preferredLeft = anchorRect.right - layerWidth;
    const maxLeft = Math.max(safeX, viewportWidth - layerWidth - safeX);
    const left = Math.min(Math.max(preferredLeft, safeX), maxLeft);
    const topForDown = anchorBottom + overlayGap;
    const topForUp = anchorTop - layerHeight - overlayGap;
    const fitsBelow = topForDown + layerHeight <= viewportHeight - safeY;
    const fitsAbove = topForUp >= safeY;

    if (fitsBelow) {
      setPositionActionOverlayPosition({ top: topForDown, left });
      return;
    }

    if (fitsAbove) {
      setPositionActionOverlayPosition({ top: topForUp, left });
      return;
    }

    const clampedTop = Math.min(
      Math.max(anchorTop - Math.max(layerHeight - anchorRect.height, 0) / 2, safeY),
      Math.max(safeY, viewportHeight - layerHeight - safeY),
    );
    setPositionActionOverlayPosition({ top: clampedTop, left });
  };

  const handlePositionActionsToggle = (
    event: ReactMouseEvent<HTMLButtonElement>,
    rowKey: string,
  ) => {
    event.stopPropagation();
    const anchorElement =
      event.currentTarget.closest<HTMLElement>("[data-position-actions-anchor='true']") ??
      event.currentTarget;

    if (openPositionActionsFor === rowKey && !pendingPositionAction) {
      clearPositionActions();
      return;
    }

    setPendingPositionAction(null);
    resolvePositionActionPlacement(rowKey, options.menuEstimate, anchorElement);
    setOpenPositionActionsFor(rowKey);
  };

  const handlePositionActionSelect = (
    event: ReactMouseEvent<HTMLButtonElement>,
    rowKey: string,
    action: TAction,
  ) => {
    event.stopPropagation();
    const anchorElement =
      event.currentTarget.closest<HTMLElement>("[data-position-actions-anchor='true']") ??
      event.currentTarget;

    setOpenPositionActionsFor(null);
    resolvePositionActionPlacement(rowKey, options.confirmEstimate, anchorElement);
    setPendingPositionAction({ rowKey, action });
  };

  const handlePositionActionCancel = (event: ReactMouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    setPendingPositionAction(null);
    setPositionActionOverlayPosition(null);
  };

  const handlePositionActionConfirm = (event: ReactMouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    setPendingPositionAction(null);
    setPositionActionOverlayPosition(null);
  };

  useEffect(() => {
    if (!openPositionActionsFor && !pendingPositionAction) {
      return undefined;
    }

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      const activeRowKey = openPositionActionsFor ?? pendingPositionAction?.rowKey ?? null;
      const activeAnchor = activeRowKey ? positionActionAnchorRefs.current[activeRowKey] : null;

      if (!positionActionsLayerRef.current?.contains(target) && !activeAnchor?.contains(target)) {
        clearPositionActions();
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        clearPositionActions();
      }
    };

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [openPositionActionsFor, pendingPositionAction]);

  useEffect(() => {
    const hasOpenActionRow =
      openPositionActionsFor !== null && options.hasRowKey(openPositionActionsFor);
    const hasPendingActionRow =
      pendingPositionAction !== null && options.hasRowKey(pendingPositionAction.rowKey);

    if (
      (openPositionActionsFor && !hasOpenActionRow) ||
      (pendingPositionAction && !hasPendingActionRow)
    ) {
      clearPositionActions();
    }
  }, [openPositionActionsFor, pendingPositionAction, options]);

  useEffect(() => {
    const activeRowKey = pendingPositionAction?.rowKey ?? openPositionActionsFor;
    if (!activeRowKey) {
      return;
    }

    const frame = requestAnimationFrame(() => {
      const layer = positionActionsLayerRef.current;
      resolvePositionActionPlacement(
        activeRowKey,
        layer
          ? { width: layer.offsetWidth, height: layer.offsetHeight }
          : pendingPositionAction
            ? options.confirmEstimate
            : options.menuEstimate,
      );
    });

    return () => {
      cancelAnimationFrame(frame);
    };
  }, [openPositionActionsFor, pendingPositionAction, options]);

  return {
    openPositionActionsFor,
    pendingPositionAction,
    positionActionOverlayPosition,
    positionActionsLayerRef,
    positionActionAnchorRefs,
    clearPositionActions,
    handlePositionActionsToggle,
    handlePositionActionSelect,
    handlePositionActionCancel,
    handlePositionActionConfirm,
  };
}
